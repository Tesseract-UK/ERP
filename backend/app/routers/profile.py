"""Employee self-service profile."""
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..database import get_db
from ..deps import client_info, get_current_user
from ..models import EmployeeDocument, User
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


@router.get("/profile/documents")
def my_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = db.query(EmployeeDocument).filter(EmployeeDocument.user_id == user.id) \
        .order_by(EmployeeDocument.created_at.desc()).all()
    return [{"id": d.id, "name": d.name, "file_path": d.file_path,
             "created_at": d.created_at.isoformat()} for d in docs]


@router.get("/files/{path:path}")
def serve_file(path: str, user: User = Depends(get_current_user)):
    """Serve uploaded documents to authenticated users."""
    abs_path = os.path.realpath(os.path.join(UPLOAD_DIR, path))
    if not abs_path.startswith(os.path.realpath(UPLOAD_DIR)) or not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(abs_path)
