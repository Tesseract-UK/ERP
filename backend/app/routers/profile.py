"""Employee self-service profile."""
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..database import get_db
from ..deps import client_info, get_current_user
from ..models import (EmployeeDocument, EmployeeRequest, EmployeeRequestParticipant,
                      LeaveRequest, RegularizationRequest, User, WFHRequest)
from ..schemas import OnboardingRequest, ProfileUpdateRequest
from ..serializers import user_full
from ..utils import audit, notify

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


@router.post("/profile/onboarding")
def complete_onboarding(body: OnboardingRequest, request: Request,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """One-time self-submission of personal details by a new employee.
    Sensitive fields become HR-managed (read-only for the employee) afterwards."""
    if user.profile_completed:
        raise HTTPException(status_code=400,
                            detail="Your profile is already complete. Contact HR for corrections.")
    for field in ("phone", "address", "emergency_contact_name", "emergency_contact_phone",
                  "date_of_birth", "pan_number", "aadhaar_number", "passport_number",
                  "bank_account", "ifsc_code"):
        value = getattr(body, field)
        if value is not None:
            setattr(user, field, value)
    user.profile_completed = True
    if user.manager_id:
        notify(db, user.manager_id, "New team member onboarded",
               f"{user.full_name} has completed their profile.", "info", actor_id=user.id)
    audit(db, user.id, "complete_onboarding", "profile",
          "First-login personal details submitted", client_info(request))
    db.commit()
    return user_full(user)


@router.get("/profile/documents")
def my_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = db.query(EmployeeDocument).filter(EmployeeDocument.user_id == user.id) \
        .order_by(EmployeeDocument.created_at.desc()).all()
    return [{"id": d.id, "name": d.name, "file_path": d.file_path,
             "created_at": d.created_at.isoformat()} for d in docs]


@router.get("/files/{path:path}")
def serve_file(path: str, request: Request, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """Serve an upload only to people entitled to see its owning record."""
    root = os.path.realpath(UPLOAD_DIR)
    abs_path = os.path.realpath(os.path.join(root, path))
    try:
        if os.path.commonpath((root, abs_path)) != root:
            raise ValueError("outside upload root")
    except ValueError:
        raise HTTPException(status_code=404, detail="File not found")
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="File not found")

    allowed = False
    owner_id = None
    for model, column in (
        (LeaveRequest, LeaveRequest.document_path),
        (WFHRequest, WFHRequest.document_path),
    ):
        record = db.query(model).filter(column == path).first()
        if record:
            owner_id = record.user_id
            allowed = user.role == "admin" or record.user_id == user.id or (
                user.role == "hr" or record.user.manager_id == user.id
            )
            break
    if not allowed:
        document = db.query(EmployeeDocument).filter(EmployeeDocument.file_path == path).first()
        if document:
            owner_id = document.user_id
            allowed = user.role in {"admin", "hr"} or document.user_id == user.id
    if not allowed:
        request_record = db.query(EmployeeRequest).filter(
            EmployeeRequest.attachment_path == path
        ).first()
        if request_record:
            owner_id = request_record.requester_id
            participant = db.query(EmployeeRequestParticipant.id).filter(
                EmployeeRequestParticipant.request_id == request_record.id,
                EmployeeRequestParticipant.user_id == user.id,
            ).first()
            allowed = user.role == "admin" or request_record.requester_id == user.id or participant is not None
    if not allowed:
        raise HTTPException(status_code=404, detail="File not found")
    if user.role == "admin":
        audit(db, user.id, "view_employee_file", "admin",
              f"Viewed a private file for employee #{owner_id}", client_info(request))
        db.commit()
    return FileResponse(abs_path)
