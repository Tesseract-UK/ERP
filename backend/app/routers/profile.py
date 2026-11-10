"""Employee self-service profile."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_info, get_current_user
from ..models import User
from ..schemas import ProfileUpdateRequest
from ..serializers import user_full
from ..utils import audit

router = APIRouter(tags=["profile"])


@router.get("/profile")
def get_profile(user: User = Depends(get_current_user)):
    return user_full(user)  # sensitive fields masked for self-view


@router.put("/profile")
def update_profile(body: ProfileUpdateRequest, request: Request,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    changed = []
    for field in ("phone", "address", "emergency_contact_name", "emergency_contact_phone"):
        value = getattr(body, field)
        if value is not None and value != getattr(user, field):
            setattr(user, field, value)
            changed.append(field)
    if changed:
        audit(db, user.id, "update_profile", "profile", ", ".join(changed),
              client_info(request))
        db.commit()
    return user_full(user)
