"""Employee leave requests and balances."""
from datetime import date, datetime
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..conversations import announce_new_request
from ..database import get_db
from ..deps import client_info, get_current_user
from ..attendance_location import attendance_now
from ..models import (
    LEAVE_TYPES, EmployeeLeavePolicy, LeaveRequest, User, WFHRequest,
)
from ..schemas import LeaveCreateRequest
from ..serializers import leave_out
from ..utils import (
    audit, is_onboarding_pending, require_request_eligibility, validate_mentions,
    working_days_between,
)

router = APIRouter(prefix="/leaves", tags=["leaves"])


def _zero_balances() -> dict:
    balances = {lt: {"allocated": 0, "used": 0.0, "remaining": 0} for lt in LEAVE_TYPES}
    balances["wfh"] = {"allocated": 0, "used": 0.0, "remaining": 0,
                       "monthly_rate": 0, "annual_cap": 0}
    return balances


def compute_balances(db: Session, user_id: int) -> dict:
    """Leave balance = annual allocation - approved usage this year, floored
    at 0. Allocation is what HR has entered for this employee; until HR
    fills it in, it is 0. The company-wide policy is only a template HR can
    copy from — it is never applied automatically.

    WFH is accrued monthly rather than granted upfront: the annual figure
    (default 24) is really "2/month" — so only monthly_rate × months elapsed
    so far this year is available, and going over it shows as a real
    negative balance (not floored) that next month's accrual reduces.

    Nobody has a balance until HR finishes onboarding them (assigns a
    manager), and Admins have none because they never request leave."""
    user = db.get(User, user_id)
    if user is None or is_onboarding_pending(user) or user.role == "admin":
        return _zero_balances()
    today = attendance_now().date()
    year_start, year_end = date(today.year, 1, 1), date(today.year, 12, 31)
    overrides = {o.leave_type: o.annual_allocation for o in db.query(EmployeeLeavePolicy)
                 .filter(EmployeeLeavePolicy.user_id == user_id).all()}

    used = dict(db.query(LeaveRequest.leave_type, func.sum(LeaveRequest.days)).filter(
        LeaveRequest.user_id == user_id, LeaveRequest.status == "approved",
        LeaveRequest.start_date >= year_start, LeaveRequest.start_date <= year_end,
    ).group_by(LeaveRequest.leave_type).all())

    wfh_used = db.query(func.count(WFHRequest.id)).filter(
        WFHRequest.user_id == user_id, WFHRequest.status == "approved",
        WFHRequest.date >= year_start, WFHRequest.date <= year_end).scalar() or 0

    balances = {}
    for lt in LEAVE_TYPES:
        alloc = overrides.get(lt, 0)
        balances[lt] = {"allocated": alloc, "used": float(used.get(lt) or 0),
                        "remaining": max(alloc - float(used.get(lt) or 0), 0)}

    wfh_annual_cap = overrides.get("wfh", 0)
    wfh_monthly_rate = round(wfh_annual_cap / 12, 2)
    wfh_accrued = round(wfh_monthly_rate * today.month, 2)  # this month's credit already counted
    balances["wfh"] = {
        "allocated": wfh_accrued, "used": float(wfh_used),
        "remaining": round(wfh_accrued - wfh_used, 2),  # not floored — can go negative
        "monthly_rate": wfh_monthly_rate, "annual_cap": wfh_annual_cap,
    }
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
def apply_leave(body: LeaveCreateRequest, request: Request,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_request_eligibility(user)
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

    mentioned_ids, mentioned_people = validate_mentions(db, user, body.mentioned_user_ids)

    req = LeaveRequest(user_id=user.id, leave_type=body.leave_type,
                       start_date=body.start_date, end_date=body.end_date,
                       days=days, reason=body.reason,
                       mentions_json=json.dumps(mentioned_ids))
    db.add(req)
    db.flush()
    announce_new_request(
        db, user, "leave", req, mentioned_people,
        f"{user.full_name} requested {days:g} day(s) of "
        f"{body.leave_type.replace('_', ' ')} leave",
    )
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
