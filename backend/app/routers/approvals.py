"""Approvals for leave, WFH and regularization requests.

The requester's assigned manager is the approver. An Admin may override and
decide any pending request. HR does not approve (unless HR is someone's
manager, which reporting-line rules do not allow).
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, aliased

from ..conversations import (
    KIND_LABEL, KIND_MODELS, app_link, audience, can_decide, heading, load_request,
    post_comment,
)
from ..database import get_db
from ..deps import client_info, require_roles
from ..models import Attendance, User
from ..schemas import DecisionRequest
from ..utils import audit, notify, notify_and_email, recompute_attendance

router = APIRouter(prefix="/approvals", tags=["approvals"])
require_approver = require_roles("manager")  # Admins always pass require_roles


@router.get("/pending")
def pending(user: User = Depends(require_approver), db: Session = Depends(get_db)):
    items = []
    requester = aliased(User)
    for kind, (model, serialize) in KIND_MODELS.items():
        q = db.query(model).join(requester, model.user_id == requester.id).filter(
            model.status == "pending", model.user_id != user.id
        )
        if user.role != "admin":
            q = q.filter(requester.manager_id == user.id)
        for r in q.order_by(model.created_at.asc()).all():
            items.append({**serialize(r, include_user=True),
                          "is_direct_report": r.user.manager_id == user.id})
    items.sort(key=lambda x: x["created_at"])
    return items


@router.get("/team-history")
def team_request_history(user: User = Depends(require_approver), db: Session = Depends(get_db)):
    """Requests from direct reports (every request, for an Admin)."""
    items = []
    for model, serialize in KIND_MODELS.values():
        query = db.query(model)
        if user.role != "admin":
            employee_ids = [row[0] for row in db.query(User.id).filter(User.manager_id == user.id).all()]
            if not employee_ids:
                return []
            query = query.filter(model.user_id.in_(employee_ids))
        items.extend(serialize(row, include_user=True)
                     for row in query.order_by(model.created_at.desc()).limit(500).all())
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items


def _apply_regularization(db: Session, req) -> None:
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
           request: Request, user: User = Depends(require_approver),
           db: Session = Depends(get_db)):
    if kind not in KIND_MODELS or decision not in ("approve", "reject"):
        raise HTTPException(status_code=404, detail="Unknown request type or action")
    # Lock the row so two approvers cannot decide the same request at once.
    req = load_request(db, kind, req_id, for_update=True)
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="This request has already been decided")
    if not can_decide(user, req):
        raise HTTPException(status_code=403,
                            detail="Only this employee's manager (or an Admin) can decide this request")

    now = datetime.utcnow()
    req.status = "approved" if decision == "approve" else "rejected"
    req.approval_stage = "complete"
    req.approver_id = user.id
    req.approver_comment = body.comment
    req.decided_at = now
    if req.user.manager_id == user.id:
        req.manager_decided_at = now
        req.manager_decided_by_id = user.id
        req.manager_comment = body.comment
    if kind == "regularization" and req.status == "approved":
        _apply_regularization(db, req)

    override = user.role == "admin" and req.user.manager_id != user.id
    verb = "approved" if req.status == "approved" else "rejected"
    text = f"{verb.title()} this request" + (" (Admin override)" if override else "")
    if body.comment:
        text += f": {body.comment}"
    post_comment(db, user, kind, req, text, [], message_type="decision")

    label = KIND_LABEL[kind]
    title = heading(kind, req)
    notify_and_email(
        db, req.user, f"{label} {verb}",
        f"Your {label.lower()} was {verb} by {user.full_name}"
        + (f": {body.comment}" if body.comment else ""),
        "approved" if verb == "approved" else "rejected",
        actor_id=user.id, entity_type=kind, entity_id=req.id,
        email_subject=f"Your {label.lower()} was {verb} — {title}",
        email_body=(
            f"Hi {req.user.full_name},\n\nYour request has been {verb} by {user.full_name}.\n\n"
            f"{title}\n" + (f"Comment: {body.comment}\n" if body.comment else "")
            + f"\nView the conversation:\n{app_link(f'/conversations?open={kind}:{req.id}')}\n\n"
            f"— Tesseract HRMS"
        ),
    )
    for other_id in audience(db, kind, req) - {req.user_id, user.id}:
        notify(db, other_id, f"{label} {verb}: {req.user.full_name}",
               f"{user.full_name} {verb} the request", "comment",
               actor_id=user.id, entity_type=kind, entity_id=req.id)
    audit(db, user.id, f"{decision}_{kind}", "approvals",
          f"{label} #{req_id} for {req.user.full_name}" + ("; admin override" if override else ""),
          client_info(request))
    db.commit()
    db.refresh(req)
    return KIND_MODELS[kind][1](req, include_user=True)
