"""In-app notifications."""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    Announcement, LeaveRequest, Notification, RegularizationRequest, User,
    WFHRequest,
)
from ..serializers import (
    announcement_out, leave_out, notification_out, regularization_out, wfh_out,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    rows = db.query(Notification).filter(Notification.user_id == user.id) \
        .order_by(Notification.created_at.desc()).limit(50).all()
    unread = db.query(func.count(Notification.id)).filter(
        Notification.user_id == user.id, Notification.is_read.is_(False)).scalar() or 0
    return {"unread": unread, "items": [notification_out(n) for n in rows]}


@router.get("/{notification_id}")
def notification_detail(notification_id: int, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    item = db.query(Notification).filter(
        Notification.id == notification_id, Notification.user_id == user.id
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Notification not found")

    result = notification_out(item)
    if item.entity_type == "announcement":
        announcement = db.get(Announcement, item.entity_id)
        if announcement is None:
            result["details_unavailable"] = True
        else:
            result["announcement"] = announcement_out(announcement)
        return result
    if item.entity_type == "employee_request":
        from .employee_requests import _get_accessible_request, _serialize
        request_record = _get_accessible_request(db, item.entity_id, user)
        result["request"] = _serialize(request_record, user, include_messages=True)
        return result
    if item.entity_type == "leave":
        model, serialize = LeaveRequest, leave_out
    elif item.entity_type == "wfh":
        model, serialize = WFHRequest, wfh_out
    elif item.entity_type == "regularization":
        model, serialize = RegularizationRequest, regularization_out
    else:
        return result

    request_record = db.get(model, item.entity_id)
    if request_record is None:
        result["details_unavailable"] = True
        return result
    owner_id = getattr(request_record, "user_id", getattr(request_record, "requester_id", None))
    authorized = (
        user.id == owner_id or user.role in {"hr", "admin"}
        or (user.role == "manager" and getattr(request_record.user, "manager_id", None) == user.id)
    )
    mentioned_ids = []
    if isinstance(request_record, (LeaveRequest, WFHRequest, RegularizationRequest)):
        try:
            mentioned_ids = json.loads(request_record.mentions_json or "[]")
        except (TypeError, ValueError):
            mentioned_ids = []
    mentioned_only = user.id in mentioned_ids and user.id != owner_id and user.role not in {"hr", "admin"} and not (
        user.role == "manager" and getattr(request_record.user, "manager_id", None) == user.id
    )
    authorized = authorized or user.id in mentioned_ids
    if not authorized:
        raise HTTPException(status_code=404, detail="Notification not found")
    request_data = serialize(request_record, include_user=True)
    if mentioned_only:
        # Tags notify colleagues without exposing private leave reasons or documents.
        request_data["reason"] = None
        request_data["document_path"] = None
    result["request"] = request_data
    return result


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.is_read = True
    db.commit()
    return {"message": "Marked as read"}


@router.post("/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.user_id == user.id,
                                  Notification.is_read.is_(False)) \
        .update({"is_read": True})
    db.commit()
    return {"message": "All notifications marked as read"}
