"""In-app notifications."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Notification, User
from ..serializers import notification_out

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    rows = db.query(Notification).filter(Notification.user_id == user.id) \
        .order_by(Notification.created_at.desc()).limit(50).all()
    unread = db.query(func.count(Notification.id)).filter(
        Notification.user_id == user.id, Notification.is_read.is_(False)).scalar() or 0
    return {"unread": unread, "items": [notification_out(n) for n in rows]}


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
