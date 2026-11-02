"""Work-from-home requests."""
from datetime import date
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_info, get_current_user
from ..attendance_location import attendance_now
from ..models import User, WFHRequest
from ..serializers import wfh_out
from ..utils import (
    audit, notify_first_approvers, notify_mentions, save_upload,
    validate_mentions,
)
from .leaves import compute_balances

router = APIRouter(prefix="/wfh", tags=["wfh"])


@router.get("")
def my_wfh(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(WFHRequest).filter(WFHRequest.user_id == user.id) \
        .order_by(WFHRequest.created_at.desc()).limit(200).all()
    return [wfh_out(r) for r in rows]


@router.post("")
def apply_wfh(request: Request, wfh_date: date = Form(..., alias="date"),
              reason: str = Form(..., min_length=3),
              mentioned_user_ids: str = Form("[]"),
              document: UploadFile | None = File(None),
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if wfh_date < attendance_now().date():
        raise HTTPException(status_code=400, detail="A past date cannot be requested for work from home")
    if wfh_date.weekday() >= 5:
        raise HTTPException(status_code=400, detail="Selected date falls on a weekend")
    existing = db.query(WFHRequest).filter(
        WFHRequest.user_id == user.id, WFHRequest.date == wfh_date,
        WFHRequest.status.in_(["pending", "approved"])).count()
    if existing:
        raise HTTPException(status_code=400,
                            detail="You already have a WFH request for this date")
    if compute_balances(db, user.id)["wfh"]["remaining"] < 1:
        raise HTTPException(status_code=400, detail="No WFH balance remaining this year")

    mentioned_ids, mentioned_people = validate_mentions(db, user, mentioned_user_ids)

    req = WFHRequest(user_id=user.id, date=wfh_date, reason=reason,
                     mentions_json=json.dumps(mentioned_ids),
                     document_path=save_upload(document, "wfh_docs"))
    db.add(req)
    db.flush()
    notify_first_approvers(
        db, user, "New WFH request",
        f"{user.full_name} requested WFH on {wfh_date.isoformat()}",
        entity_type="wfh", entity_id=req.id,
    )
    approver_ids = {n.user_id for n in db.new if getattr(n, "kind", None) == "approval"}
    notify_mentions(
        db, user, mentioned_people, entity_type="wfh", entity_id=req.id,
        message=f"{user.full_name} mentioned you in a WFH request for {wfh_date.isoformat()}",
        already_notified_ids=approver_ids,
    )
    audit(db, user.id, "apply_wfh", "wfh", f"WFH on {wfh_date}", client_info(request))
    db.commit()
    db.refresh(req)
    return wfh_out(req)


@router.post("/{wfh_id}/cancel")
def cancel_wfh(wfh_id: int, request: Request,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import datetime
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
