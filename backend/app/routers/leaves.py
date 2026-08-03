"""Employee leave requests and balances."""
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_info, get_current_user
from ..models import LEAVE_TYPES, LeavePolicy, LeaveRequest, User, WFHRequest
from ..schemas import LeaveCreateRequest
from ..serializers import leave_out
from ..utils import audit, notify, save_upload, working_days_between

router = APIRouter(prefix="/leaves", tags=["leaves"])


def compute_balances(db: Session, user_id: int) -> dict:
    """Balance = policy allocation - approved usage in the current year."""
    year_start, year_end = date(date.today().year, 1, 1), date(date.today().year, 12, 31)
    policies = {p.leave_type: p.annual_allocation for p in db.query(LeavePolicy).all()}

    used = dict(db.query(LeaveRequest.leave_type, func.sum(LeaveRequest.days)).filter(
        LeaveRequest.user_id == user_id, LeaveRequest.status == "approved",
        LeaveRequest.start_date >= year_start, LeaveRequest.start_date <= year_end,
    ).group_by(LeaveRequest.leave_type).all())

    wfh_used = db.query(func.count(WFHRequest.id)).filter(
        WFHRequest.user_id == user_id, WFHRequest.status == "approved",
        WFHRequest.date >= year_start, WFHRequest.date <= year_end).scalar() or 0

    balances = {}
    for lt in LEAVE_TYPES:
        alloc = policies.get(lt, 0)
        balances[lt] = {"allocated": alloc, "used": float(used.get(lt) or 0),
                        "remaining": max(alloc - float(used.get(lt) or 0), 0)}
    wfh_alloc = policies.get("wfh", 0)
    balances["wfh"] = {"allocated": wfh_alloc, "used": float(wfh_used),
                       "remaining": max(wfh_alloc - wfh_used, 0)}
    return balances


@router.get("/balance")
def balance(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return compute_balances(db, user.id)


@router.get("")
def my_leaves(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(LeaveRequest).filter(LeaveRequest.user_id == user.id) \
        .order_by(LeaveRequest.created_at.desc()).limit(200).all()
    return [leave_out(r) for r in rows]


@router.post("")
def apply_leave(request: Request,
                leave_type: str = Form(...), start_date: date = Form(...),
                end_date: date = Form(...), reason: str = Form(...),
                document: UploadFile | None = File(None),
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = LeaveCreateRequest(leave_type=leave_type, start_date=start_date,
                              end_date=end_date, reason=reason)
    days = working_days_between(db, body.start_date, body.end_date)
    if days <= 0:
        raise HTTPException(status_code=400,
                            detail="The selected range contains no working days")

    overlapping = db.query(LeaveRequest).filter(
        LeaveRequest.user_id == user.id,
        LeaveRequest.status.in_(["pending", "approved"]),
        LeaveRequest.start_date <= body.end_date,
        LeaveRequest.end_date >= body.start_date).count()
    if overlapping:
        raise HTTPException(status_code=400,
                            detail="You already have a leave request overlapping these dates")

    if body.leave_type != "unpaid":
        remaining = compute_balances(db, user.id)[body.leave_type]["remaining"]
        if days > remaining:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient balance: {remaining} day(s) remaining for this leave type")

    req = LeaveRequest(user_id=user.id, leave_type=body.leave_type,
                       start_date=body.start_date, end_date=body.end_date,
                       days=days, reason=body.reason,
                       document_path=save_upload(document, "leave_docs"))
    db.add(req)
    if user.manager_id:
        notify(db, user.manager_id, "New leave request",
               f"{user.full_name} requested {days} day(s) of "
               f"{body.leave_type.replace('_', ' ')} leave", "approval")
    audit(db, user.id, "apply_leave", "leaves",
          f"{body.leave_type} {body.start_date} → {body.end_date}", client_info(request))
    db.commit()
    db.refresh(req)
    return leave_out(req)


@router.post("/{leave_id}/cancel")
def cancel_leave(leave_id: int, request: Request,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = db.get(LeaveRequest, leave_id)
    if req is None or req.user_id != user.id:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be cancelled")
    req.status = "cancelled"
    req.decided_at = datetime.utcnow()
    audit(db, user.id, "cancel_leave", "leaves", f"Leave #{leave_id}", client_info(request))
    db.commit()
    return leave_out(req)
