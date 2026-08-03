"""Manager/HR/Admin approvals for leave, WFH and regularization requests."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

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


@router.get("/pending")
def pending(user: User = Depends(require_manager), db: Session = Depends(get_db)):
    items = []
    for kind, (model, serialize) in MODELS.items():
        q = db.query(model).filter(model.status == "pending")
        if user.role == "manager":
            q = q.join(User, model.user_id == User.id).filter(User.manager_id == user.id)
        items.extend(serialize(r, include_user=True)
                     for r in q.order_by(model.created_at.asc()).limit(200).all())
    items.sort(key=lambda x: x["created_at"])
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
    att.notes = f"Regularized: {req.reason}"[:500]
    recompute_attendance(att)


@router.post("/{kind}/{req_id}/{decision}")
def decide(kind: str, req_id: int, decision: str, body: DecisionRequest,
           request: Request, user: User = Depends(require_manager),
           db: Session = Depends(get_db)):
    if kind not in MODELS or decision not in ("approve", "reject"):
        raise HTTPException(status_code=404, detail="Unknown request type or action")
    model, serialize = MODELS[kind]
    req = db.get(model, req_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    _scope_check(user, req)
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="This request has already been decided")

    req.status = "approved" if decision == "approve" else "rejected"
    req.approver_id = user.id
    req.approver_comment = body.comment
    req.decided_at = datetime.utcnow()

    if kind == "regularization" and req.status == "approved":
        _apply_regularization(db, req)

    label = {"leave": "Leave request", "wfh": "WFH request",
             "regularization": "Regularization request"}[kind]
    notify(db, req.user_id, f"{label} {req.status}",
           f"Your {label.lower()} was {req.status} by {user.full_name}"
           + (f": {body.comment}" if body.comment else ""),
           "approved" if req.status == "approved" else "rejected")
    audit(db, user.id, f"{decision}_{kind}", "approvals",
          f"{label} #{req_id} for {req.user.full_name}", client_info(request))
    db.commit()
    db.refresh(req)
    return serialize(req, include_user=True)
