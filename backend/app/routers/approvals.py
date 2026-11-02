"""Manager/HR/Admin approvals for leave, WFH and regularization requests."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from sqlalchemy.orm import aliased

from ..database import get_db
from ..deps import client_info, require_manager
from ..models import (
    Attendance, LeaveRequest, RegularizationRequest, User, WFHRequest,
)
from ..schemas import DecisionRequest
from ..serializers import leave_out, regularization_out, wfh_out
from ..utils import audit, notify, recompute_attendance

router = APIRouter(prefix="/approvals", tags=["approvals"])

MODELS = {"leave": (LeaveRequest, leave_out),
          "wfh": (WFHRequest, wfh_out),
          "regularization": (RegularizationRequest, regularization_out)}


def _scope_check(approver: User, req) -> None:
    """Managers may only act on direct reports; HR/Admin may act on anyone."""
    if approver.role in ("hr", "admin"):
        return
    if req.user.manager_id != approver.id:
        raise HTTPException(status_code=403,
                            detail="This request does not belong to your team")


def _active_manager(db: Session, req) -> User | None:
    manager = db.get(User, req.user.manager_id) if req.user.manager_id else None
    return manager if manager and manager.is_active and manager.role == "manager" else None


def _active_hr_exists(db: Session) -> bool:
    return db.query(User.id).filter(User.role == "hr", User.is_active.is_(True)).first() is not None


def _may_decide(db: Session, user: User, req) -> bool:
    stage = req.approval_stage or "pending_manager"  # old rows created before migration
    manager = _active_manager(db, req)
    hr_exists = _active_hr_exists(db)
    if user.role == "manager":
        return stage == "pending_manager" and manager is not None and manager.id == user.id
    if user.role == "hr":
        return stage == "pending_hr" or (stage == "pending_manager" and manager is None)
    if user.role == "admin":
        # Admin can make a final decision at either stage without waiting for
        # the manager/HR chain; the action is recorded in approver/audit fields.
        return req.status == "pending"
    return False


@router.get("/pending")
def pending(user: User = Depends(require_manager), db: Session = Depends(get_db)):
    items = []
    requester = aliased(User)
    manager = aliased(User)
    for kind, (model, serialize) in MODELS.items():
        q = db.query(model).join(requester, model.user_id == requester.id).filter(
            model.status == "pending"
        )
        pending_manager = or_(model.approval_stage == "pending_manager",
                              model.approval_stage.is_(None))
        if user.role == "manager":
            q = q.filter(requester.manager_id == user.id, pending_manager)
        elif user.role == "hr":
            q = q.outerjoin(manager, requester.manager_id == manager.id).filter(
                or_(
                    model.approval_stage == "pending_hr",
                    and_(pending_manager, or_(
                        manager.id.is_(None), manager.is_active.is_(False),
                        manager.role != "manager",
                    )),
                )
            )
        candidates = q.order_by(model.created_at.asc()).all()
        items.extend(serialize(r, include_user=True) for r in candidates)
    items.sort(key=lambda x: x["created_at"])
    return items


@router.get("/team-history")
def team_request_history(user: User = Depends(require_manager), db: Session = Depends(get_db)):
    """Requests for current direct reports, including items already approved by the Manager."""
    employee_ids = None
    if user.role == "manager":
        employee_ids = [row[0] for row in db.query(User.id).filter(
            User.manager_id == user.id
        ).all()]
        if not employee_ids:
            return []
    else:
        return []

    items = []
    for model, serialize in MODELS.values():
        query = db.query(model)
        if employee_ids is not None:
            query = query.filter(model.user_id.in_(employee_ids))
        items.extend(serialize(row, include_user=True)
                     for row in query.order_by(model.created_at.desc()).all())
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items


def _apply_regularization(db: Session, req: RegularizationRequest) -> None:
    """Write the approved corrected times into the attendance record."""
    att = db.query(Attendance).filter(Attendance.user_id == req.user_id,
                                      Attendance.date == req.date).first()
    if att is None:
        att = Attendance(user_id=req.user_id, date=req.date, status="present")
        db.add(att)
        db.flush()
    if req.requested_check_in:
        att.check_in = req.requested_check_in
    if req.requested_check_out:
        att.check_out = req.requested_check_out
    att.status = "present"
    # An approved, employee-submitted regularization supersedes an Admin's
    # earlier presence/absence correction for this date. Keep that action in
    # audit_logs, but do not let its cached override win over the approval.
    att.status_override = None
    att.status_override_reason = None
    att.status_override_by_id = None
    att.status_override_at = None
    att.notes = f"Regularized: {req.reason}"[:500]
    recompute_attendance(att)


@router.post("/{kind}/{req_id}/{decision}")
def decide(kind: str, req_id: int, decision: str, body: DecisionRequest,
           request: Request, user: User = Depends(require_manager),
           db: Session = Depends(get_db)):
    if kind not in MODELS or decision not in ("approve", "reject"):
        raise HTTPException(status_code=404, detail="Unknown request type or action")
    model, serialize = MODELS[kind]
    # Serialize competing approvals so two users cannot decide the same stale
    # pending stage concurrently in the production database.
    req = db.query(model).filter(model.id == req_id).with_for_update().first()
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    _scope_check(user, req)
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="This request has already been decided")
    if not _may_decide(db, user, req):
        raise HTTPException(status_code=403, detail="You are not the approver for the current stage")

    stage = req.approval_stage or "pending_manager"
    now = datetime.utcnow()
    if user.role == "manager":
        req.manager_decided_at = now
        req.manager_decided_by_id = user.id
        req.manager_comment = body.comment
    elif user.role == "hr":
        req.hr_decided_at = now
        req.hr_comment = body.comment

    if decision == "reject":
        req.status = "rejected"
        req.approval_stage = "complete"
    elif stage == "pending_manager" and user.role == "manager":
        req.approval_stage = "pending_hr"
        notify(db, req.user_id, "Request sent to HR", f"{user.full_name} approved your request; HR review is next.", "approval",
               actor_id=user.id, entity_type=kind, entity_id=req.id)
    else:
        req.status = "approved"
        req.approval_stage = "complete"
    req.approver_id = user.id
    req.approver_comment = body.comment
    if req.status in ("approved", "rejected"):
        req.decided_at = now

    if kind == "regularization" and req.status == "approved":
        _apply_regularization(db, req)

    label = {"leave": "Leave request", "wfh": "WFH request",
             "regularization": "Regularization request"}[kind]
    if req.status in ("approved", "rejected"):
        notify(db, req.user_id, f"{label} {req.status}",
               f"Your {label.lower()} was {req.status} by {user.full_name}"
               + (f": {body.comment}" if body.comment else ""),
               "approved" if req.status == "approved" else "rejected",
               actor_id=user.id, entity_type=kind, entity_id=req.id)
    elif req.approval_stage == "pending_hr":
        reviewers = db.query(User).filter(
            User.role == "hr", User.is_active.is_(True)
        ).all()
        if not reviewers:
            reviewers = db.query(User).filter(
                User.role == "admin", User.is_active.is_(True)
            ).all()
        for reviewer in reviewers:
            notify(db, reviewer.id, f"{label} needs HR review",
                   f"{req.user.full_name}'s request is awaiting the required HR decision.", "approval",
                   actor_id=user.id, entity_type=kind, entity_id=req.id)
    audit(db, user.id, f"{decision}_{kind}", "approvals",
          f"{label} #{req_id} for {req.user.full_name}; stage={stage}", client_info(request))
    db.commit()
    db.refresh(req)
    return serialize(req, include_user=True)
