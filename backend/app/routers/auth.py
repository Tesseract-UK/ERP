"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_info, get_current_user
from ..models import User
from ..schemas import ChangePasswordRequest, LoginRequest, SetPasswordRequest
from ..security import create_access_token, hash_password, verify_password
from ..serializers import user_full
from ..utils import audit, check_email_domain

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    check_email_domain(body.email)
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Your account has been deactivated. Contact HR.")
    audit(db, user.id, "login", "auth", client=client_info(request))
    db.commit()
    return {
        "access_token": create_access_token(user.id, user.role),
        "token_type": "bearer",
        "user": user_full(user),
    }


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_full(user)


@router.post("/change-password")
def change_password(body: ChangePasswordRequest, request: Request,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    audit(db, user.id, "change_password", "auth", client=client_info(request))
    db.commit()
    return {"message": "Password updated successfully"}


@router.post("/set-password")
def set_password(body: SetPasswordRequest, request: Request,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """First-login forced password change; only valid while the flag is set."""
    if not user.must_change_password:
        raise HTTPException(status_code=400,
                            detail="Use change-password with your current password instead")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    audit(db, user.id, "set_password_first_login", "auth", client=client_info(request))
    db.commit()
    return user_full(user)
