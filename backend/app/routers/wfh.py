"""Work-from-home requests."""
from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..conversations import announce_new_request
from ..database import get_db
from ..deps import client_info, get_current_user
from ..attendance_location import attendance_now
from ..models import CompanyWFHDay, Holiday, User, WFHRequest
from ..schemas import WFHCreateRequest
from ..serializers import wfh_out
from ..utils import audit, require_request_eligibility, validate_mentions
from .leaves import compute_balances

router = APIRouter(prefix="/wfh", tags=["wfh"])


@router.get("")
def my_wfh(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(WFHRequest).filter(WFHRequest.user_id == user.id) \
        .order_by(WFHRequest.created_at.desc()).limit(200).all()
    return [wfh_out(r) for r in rows]


@router.post("")
def apply_wfh(body: WFHCreateRequest, request: Request,
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_request_eligibility(user)
    wfh_date = body.date
    if wfh_date < attendance_now().date():
        raise HTTPException(status_code=400, detail="A past date cannot be requested for work from home")
    if wfh_date.weekday() >= 5:
        raise HTTPException(status_code=400, detail="Selected date falls on a weekend")
    if db.query(Holiday.id).filter(Holiday.date == wfh_date,
                                   Holiday.holiday_type != "optional").first():
        raise HTTPException(status_code=400, detail="Selected date is a company holiday")
    if db.query(CompanyWFHDay.id).filter(CompanyWFHDay.date == wfh_date).first():
        raise HTTPException(status_code=400,
                            detail="This date is already a company-wide work-from-home day")
    existing = db.query(WFHRequest).filter(
        WFHRequest.user_id == user.id, WFHRequest.date == wfh_date,
        WFHRequest.status.in_(["pending", "approved"])).count()
    if existing:
        raise HTTPException(status_code=400,
                            detail="You already have a WFH request for this date")
    if compute_balances(db, user.id)["wfh"]["remaining"] < 1:
        raise HTTPException(status_code=400, detail="No WFH balance remaining this year")

    mentioned_ids, mentioned_people = validate_mentions(db, user, body.mentioned_user_ids)

    req = WFHRequest(user_id=user.id, date=wfh_date, reason=body.reason,
                     mentions_json=json.dumps(mentioned_ids))
    db.add(req)
    db.flush()
    announce_new_request(db, user, "wfh", req, mentioned_people,
                         f"{user.full_name} requested WFH on {wfh_date.isoformat()}")
    audit(db, user.id, "apply_wfh", "wfh", f"WFH on {wfh_date}", client_info(request))
    db.commit()
    db.refresh(req)
    return wfh_out(req)


@router.post("/{wfh_id}/cancel")
def cancel_wfh(wfh_id: int, request: Request,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = db.get(WFHRequest, wfh_id)
    if req is None or req.user_id != user.id:
        raise HTTPException(status_code=404, detail="WFH request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be cancelled")
    req.status = "cancelled"
    req.decided_at = datetime.utcnow()
    audit(db, user.id, "cancel_wfh", "wfh", f"WFH #{wfh_id}", client_info(request))
    db.commit()
    return wfh_out(req)
