"""Attendance regularization requests (missed check-in / check-out)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_info, get_current_user
from ..models import RegularizationRequest, User
from ..schemas import RegularizationCreateRequest
from ..serializers import regularization_out
from ..utils import audit, notify, parse_dt

router = APIRouter(prefix="/regularization", tags=["regularization"])


@router.get("")
def my_requests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(RegularizationRequest) \
        .filter(RegularizationRequest.user_id == user.id) \
        .order_by(RegularizationRequest.created_at.desc()).limit(200).all()
    return [regularization_out(r) for r in rows]


@router.post("")
def create_request(body: RegularizationCreateRequest, request: Request,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.date > date.today():
        raise HTTPException(status_code=400, detail="Cannot regularize a future date")
    check_in = parse_dt(body.requested_check_in)
    check_out = parse_dt(body.requested_check_out)
    if check_in is None and check_out is None:
        raise HTTPException(status_code=400,
                            detail="Provide a corrected check-in and/or check-out time")
    if check_in and check_out and check_out <= check_in:
        raise HTTPException(status_code=400, detail="Check-out must be after check-in")

    pending = db.query(RegularizationRequest).filter(
        RegularizationRequest.user_id == user.id,
        RegularizationRequest.date == body.date,
        RegularizationRequest.status == "pending").count()
    if pending:
        raise HTTPException(status_code=400,
                            detail="A pending regularization already exists for this date")

    req = RegularizationRequest(user_id=user.id, date=body.date,
                                requested_check_in=check_in,
                                requested_check_out=check_out, reason=body.reason)
    db.add(req)
    if user.manager_id:
        notify(db, user.manager_id, "New regularization request",
               f"{user.full_name} requested attendance regularization for "
               f"{body.date.isoformat()}", "approval")
    audit(db, user.id, "apply_regularization", "regularization",
          f"For {body.date}", client_info(request))
    db.commit()
    db.refresh(req)
    return regularization_out(req)
