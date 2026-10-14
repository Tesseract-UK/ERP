"""Authentication endpoints for Google OAuth and HRMS accounts."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import COOKIE_SAMESITE, COOKIE_SECURE, FRONTEND_URL
from ..database import get_db
from ..deps import client_info, get_current_user
from ..google_auth import (
    build_google_authorization_url,
    exchange_code_for_tokens,
    verify_google_id_token,
)
from ..models import User
from ..schemas import (
    ChangePasswordRequest,
    LoginRequest,
    SetPasswordRequest,
    SignupRequest,
)
from ..security import create_access_token, hash_password, verify_password
from ..serializers import user_full
from ..utils import audit, check_email_domain, generate_employee_code, notify


router = APIRouter(prefix="/auth", tags=["auth"])

STATE_COOKIE = "hrms_google_oauth_state"
SESSION_COOKIE = "hrms_session"


def _set_session_cookie(response: Response, token: str) -> None:
    """Set the signed HRMS token in an HttpOnly browser cookie."""
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=60 * 60 * 8,
        path="/",
    )


def _clear_state_cookie(response: Response) -> None:
    """Remove the short-lived Google OAuth state cookie."""
    response.delete_cookie(
        key=STATE_COOKIE,
        path="/auth/google",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite=COOKIE_SAMESITE,
    )


def _login_error_redirect(error: str) -> RedirectResponse:
    """Redirect to login using a non-sensitive error code."""
    response = RedirectResponse(
        url=f"{FRONTEND_URL}/login?error={error}",
        status_code=303,
    )
    _clear_state_cookie(response)
    return response


@router.get("/google/login")
def google_login():
    """Start Google OAuth and save a short-lived state value in a cookie."""
    state = secrets.token_urlsafe(32)

    try:
        authorization_url = build_google_authorization_url(state)
    except HTTPException as exc:
        if exc.status_code == 503:
            return _login_error_redirect("google_not_configured")
        raise

    response = RedirectResponse(
        url=authorization_url,
        status_code=302,
    )

    response.set_cookie(
        key=STATE_COOKIE,
        value=state,
        max_age=600,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/auth/google",
    )

    return response


@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Verify Google identity and establish an HRMS session."""
    saved_state = request.cookies.get(STATE_COOKIE)

    if error:
        return _login_error_redirect("google_login_cancelled")

    if not code or not state or not saved_state:
        return _login_error_redirect("google_login_incomplete")

    if not secrets.compare_digest(state, saved_state):
        return _login_error_redirect("google_state_invalid")

    try:
        token_response = exchange_code_for_tokens(code)
        claims = verify_google_id_token(token_response["id_token"])

    except HTTPException as exc:
        if exc.status_code == 503:
            return _login_error_redirect("google_not_configured")
        return _login_error_redirect("google_login_failed")

    except Exception:
        return _login_error_redirect("google_login_failed")

    email_claim = claims.get("email")
    google_sub_claim = claims.get("sub")

    if not isinstance(email_claim, str) or not email_claim.strip():
        return _login_error_redirect("google_login_failed")

    if not isinstance(google_sub_claim, str) or not google_sub_claim.strip():
        return _login_error_redirect("google_login_failed")

    email = email_claim.strip().lower()
    google_sub = google_sub_claim.strip()

    try:
        check_email_domain(email)
    except HTTPException as exc:
        if exc.status_code in (400, 403):
            return _login_error_redirect("email_domain_not_allowed")
        return _login_error_redirect("google_login_failed")

    try:
        user = (
            db.query(User)
            .filter(User.google_sub == google_sub)
            .first()
        )

        if user is not None:
            if user.email.strip().lower() != email:
                db.rollback()
                return _login_error_redirect("google_account_mismatch")

        else:
            user = (
                db.query(User)
                .filter(User.email == email)
                .first()
            )

            if user is not None:
                existing_google_sub = user.google_sub

                if existing_google_sub and existing_google_sub != google_sub:
                    db.rollback()
                    return _login_error_redirect("google_account_mismatch")

                user.google_sub = google_sub

            else:
                # New Google accounts receive employee access only.
                # HR/Admin roles must be assigned through HRMS administration.
                display_name = (
                    claims.get("name")
                    or claims.get("given_name")
                    or email.split("@", 1)[0]
                ).strip()

                user = User(
                    email=email,
                    full_name=display_name[:150],
                    employee_code=generate_employee_code(db),
                    password_hash=hash_password(secrets.token_urlsafe(48)),
                    role="employee",
                    profile_completed=False,
                    google_sub=google_sub,
                )

                db.add(user)

        if not user.is_active:
            db.rollback()
            return _login_error_redirect("account_deactivated")

        db.flush()

        audit(
            db,
            user.id,
            "google_login",
            "auth",
            f"Google sign-in: {email}",
            client=client_info(request),
        )

        db.commit()
        db.refresh(user)

    except Exception:
        db.rollback()
        return _login_error_redirect("google_login_failed")

    token = create_access_token(user.id, user.role)

    response = RedirectResponse(
        url=f"{FRONTEND_URL}/",
        status_code=303,
    )

    _set_session_cookie(response, token)
    _clear_state_cookie(response)

    return response


@router.post("/logout", status_code=204)
def logout():
    """Clear the browser's HRMS session and OAuth state cookies."""
    response = Response(status_code=204)

    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite=COOKIE_SAMESITE,
    )

    _clear_state_cookie(response)

    return response


@router.post("/signup")
def signup(
    body: SignupRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create a standard employee account."""
    check_email_domain(body.email)
    email = body.email.strip().lower()

    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists",
        )

    user = User(
        email=email,
        full_name=body.full_name,
        employee_code=generate_employee_code(db),
        password_hash=hash_password(body.password),
        role="employee",
    )

    db.add(user)
    db.flush()

    audit(
        db,
        user.id,
        "signup",
        "auth",
        f"Self-signup: {body.full_name} ({email})",
        client=client_info(request),
    )

    db.commit()
    db.refresh(user)

    return {
        "access_token": create_access_token(user.id, user.role),
        "token_type": "bearer",
        "user": user_full(user),
    }


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate any active HRMS role using email and password."""
    email = body.email.strip().lower()

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if user is None or not verify_password(
        body.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Your account has been deactivated. Contact HR.",
        )

    audit(
        db,
        user.id,
        "login",
        "auth",
        client=client_info(request),
    )

    db.commit()

    return {
        "access_token": create_access_token(user.id, user.role),
        "token_type": "bearer",
        "user": user_full(user),
    }


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    """Return the currently authenticated HRMS user."""
    return user_full(user)


@router.post("/password-change-request")
def request_password_change(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ask administrators for permission to change the password."""
    if user.must_change_password:
        raise HTTPException(
            status_code=400,
            detail=(
                "A password change is already approved — "
                "sign out and back in to set it"
            ),
        )

    admins = (
        db.query(User)
        .filter(
            User.role == "admin",
            User.is_active.is_(True),
        )
        .all()
    )

    for admin in admins:
        notify(
            db,
            admin.id,
            "Password change request",
            (
                f"{user.full_name} ({user.employee_code}) requests permission "
                "to change their password. Approve it from the Employees page."
            ),
            "approval",
        )

    audit(
        db,
        user.id,
        "request_password_change",
        "auth",
        client=client_info(request),
    )

    db.commit()

    return {
        "message": (
            "Request sent to the administrators. "
            "You will be notified once approved."
        )
    }


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change an admin password directly, subject to company policy."""
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail=(
                "Password changes require admin approval. "
                "Use 'Request password change' on your profile page."
            ),
        )

    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect",
        )

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False

    audit(
        db,
        user.id,
        "change_password",
        "auth",
        client=client_info(request),
    )

    db.commit()

    return {"message": "Password updated successfully"}


@router.post("/set-password")
def set_password(
    body: SetPasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Handle the forced first-login password change."""
    if not user.must_change_password:
        raise HTTPException(
            status_code=400,
            detail="Use change-password with your current password instead",
        )

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False

    audit(
        db,
        user.id,
        "set_password_first_login",
        "auth",
        client=client_info(request),
    )

    db.commit()
    db.refresh(user)

    return user_full(user)