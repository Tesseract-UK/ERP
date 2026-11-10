"""Attendance regularization requests (missed check-in / check-out)."""
from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..conversations import announce_new_request
from ..database import get_db
from ..deps import client_info, get_current_user
from ..attendance_location import attendance_now
from ..models import RegularizationRequest, User
from ..schemas import RegularizationCreateRequest
from ..serializers import regularization_out
from ..utils import audit, parse_dt, require_request_eligibility, validate_mentions

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
    require_request_eligibility(user)
    if body.date > attendance_now().date():
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

    mentioned_ids, mentioned_people = validate_mentions(db, user, body.mentioned_user_ids)

    req = RegularizationRequest(user_id=user.id, date=body.date,
                                requested_check_in=check_in,
                                requested_check_out=check_out, reason=body.reason,
                                mentions_json=json.dumps(mentioned_ids))
    db.add(req)
    db.flush()
    announce_new_request(
        db, user, "regularization", req, mentioned_people,
        f"{user.full_name} requested attendance regularization for {body.date.isoformat()}",
    )
    audit(db, user.id, "apply_regularization", "regularization",
          f"For {body.date}", client_info(request))
    db.commit()
    db.refresh(req)
    return regularization_out(req)


@router.post("/{req_id}/cancel")
def cancel_request(req_id: int, request: Request,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = db.get(RegularizationRequest, req_id)
    if req is None or req.user_id != user.id:
        raise HTTPException(status_code=404, detail="Regularization request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be cancelled")
    req.status = "cancelled"
    req.decided_at = datetime.utcnow()
    audit(db, user.id, "cancel_regularization", "regularization",
          f"Regularization #{req_id}", client_info(request))
    db.commit()
    return regularization_out(req)
