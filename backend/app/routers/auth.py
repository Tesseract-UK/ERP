"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_info, get_current_user
from ..models import User
from ..schemas import ChangePasswordRequest, LoginRequest, SetPasswordRequest, SignupRequest
from ..security import create_access_token, hash_password, verify_password
from ..serializers import user_full
from ..utils import audit, check_email_domain, generate_employee_code, notify

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup")
def signup(body: SignupRequest, request: Request, db: Session = Depends(get_db)):
    """Self-service account creation. Anyone with an allowed company email
    domain can register and is signed in immediately — no admin approval."""
    check_email_domain(body.email)
    email = body.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    user = User(
        email=email,
        full_name=body.full_name,
        employee_code=generate_employee_code(db),
        password_hash=hash_password(body.password),
        role="employee",
    )
    db.add(user)
    audit(db, None, "signup", "auth", f"Self-signup: {body.full_name} ({email})",
          client=client_info(request))
    db.commit()
    db.refresh(user)
    return {
        "access_token": create_access_token(user.id, user.role),
        "token_type": "bearer",
        "user": user_full(user),
    }


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


@router.post("/password-change-request")
def request_password_change(request: Request, user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    """Ask the admins for permission to change the password."""
    if user.must_change_password:
        raise HTTPException(status_code=400,
                            detail="A password change is already approved — sign out and back in to set it")
    admins = db.query(User).filter(User.role == "admin", User.is_active.is_(True)).all()
    for a in admins:
        notify(db, a.id, "Password change request",
               f"{user.full_name} ({user.employee_code}) requests permission to "
               f"change their password. Approve it from the Employees page.", "approval")
    audit(db, user.id, "request_password_change", "auth", client=client_info(request))
    db.commit()
    return {"message": "Request sent to the administrators. You will be notified once approved."}


@router.post("/change-password")
def change_password(body: ChangePasswordRequest, request: Request,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Company policy: only admins may change their password directly; everyone
    # else goes through request → admin approval → forced reset at next login.
    if user.role != "admin":
        raise HTTPException(status_code=403,
                            detail="Password changes require admin approval. "
                                   "Use 'Request password change' on your profile page.")
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
