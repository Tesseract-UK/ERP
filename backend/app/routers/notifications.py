"""In-app notifications."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..conversations import KIND_MODELS, can_view, conversation_out, load_request
from ..database import get_db
from ..deps import get_current_user
from ..models import Announcement, Notification, User
from ..serializers import announcement_out, notification_out

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
    if item.entity_type in KIND_MODELS:
        try:
            record = load_request(db, item.entity_type, item.entity_id)
        except HTTPException:
            result["details_unavailable"] = True
            return result
        if not can_view(db, user, item.entity_type, record):
            result["details_unavailable"] = True
            return result
        result["conversation"] = conversation_out(db, user, item.entity_type, record)
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
