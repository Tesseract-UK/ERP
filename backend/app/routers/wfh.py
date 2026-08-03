"""Work-from-home requests."""
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_info, get_current_user
from ..models import User, WFHRequest
from ..serializers import wfh_out
from ..utils import audit, notify, save_upload
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
              document: UploadFile | None = File(None),
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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

    req = WFHRequest(user_id=user.id, date=wfh_date, reason=reason,
                     document_path=save_upload(document, "wfh_docs"))
    db.add(req)
    if user.manager_id:
        notify(db, user.manager_id, "New WFH request",
               f"{user.full_name} requested WFH on {wfh_date.isoformat()}", "approval")
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
