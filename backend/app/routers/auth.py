"""Authentication endpoints for Google OAuth and HRMS accounts."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    AUTH_SESSION_MAX_DAYS,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    FRONTEND_URL,
)
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
    SignupRequest,
    SetPasswordRequest,
)
from ..security import hash_password, verify_password
from ..session_service import (
    create_user_session,
    revoke_refresh_session,
    revoke_token_session,
    revoke_user_sessions,
    rotate_refresh_token,
    session_id_from_token,
)
from ..serializers import user_full
from ..utils import audit, check_email_domain


router = APIRouter(prefix="/auth", tags=["auth"])

STATE_COOKIE = "hrms_google_oauth_state"
SESSION_COOKIE = "hrms_session"
REFRESH_COOKIE = "hrms_refresh"
GOOGLE_PROVISIONING_ATTEMPTS = 3


def _registration_employee_code(db: Session, user: User) -> str:
    """Allocate a stable employee code from the database-generated user ID.

    Unlike count + 1, primary keys are allocated atomically by the database,
    so parallel registrations do not compete for the same employee code.
    """
    base = f"EMP{user.id:06d}"
    collision = (
        db.query(User.id)
        .filter(User.employee_code == base, User.id != user.id)
        .first()
    )
    if collision:
        # HR may have manually assigned a code matching this user's ID.
        return f"{base}-{secrets.token_hex(4).upper()}"
    return base


def _link_or_create_google_user(
    db: Session,
    email: str,
    google_sub: str,
    claims: dict,
    request: Request,
) -> tuple[User | None, str | None]:
    """Idempotently link or provision a verified Google identity.

    Unique DB indexes on email and google_sub arbitrate simultaneous callbacks.
    A losing callback rolls back and retries, then finds the account created by
    the winning transaction instead of failing a legitimate sign-in.
    """
    for attempt in range(GOOGLE_PROVISIONING_ATTEMPTS):
        try:
            user = db.query(User).filter(User.google_sub == google_sub).first()

            if user is not None:
                if user.email.strip().lower() != email:
                    db.rollback()
                    return None, "google_account_mismatch"
            else:
                user = db.query(User).filter(User.email == email).first()

                if user is not None:
                    if user.google_sub and user.google_sub != google_sub:
                        db.rollback()
                        return None, "google_account_mismatch"
                    user.google_sub = google_sub
                else:
                    # Google has already verified mailbox ownership and the
                    # organization domain. New accounts receive employee role.
                    display_name = (
                        claims.get("name")
                        or claims.get("given_name")
                        or email.split("@", 1)[0]
                    ).strip()
                    user = User(
                        # Temporary unique code lets the DB allocate its
                        # primary key before deriving the stable employee code.
                        employee_code=f"NEW{secrets.token_hex(8).upper()}",
                        email=email,
                        full_name=display_name[:150],
                        password_hash=hash_password(secrets.token_urlsafe(48)),
                        role="employee",
                        is_active=True,
                        profile_completed=False,
                        google_sub=google_sub,
                    )
                    db.add(user)
                    db.flush()
                    user.employee_code = _registration_employee_code(db, user)

            if not user.is_active:
                db.rollback()
                return None, "account_deactivated"

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
            return user, None

        except IntegrityError:
            # Another callback may have inserted this email/sub or an employee
            # code at the same time. Roll back before re-reading the winner.
            db.rollback()
            if attempt + 1 == GOOGLE_PROVISIONING_ATTEMPTS:
                return None, "google_login_failed"
        except Exception:
            db.rollback()
            return None, "google_login_failed"

    return None, "google_login_failed"


def _set_session_cookies(
    response: Response, access_token: str, refresh_token: str
) -> None:
    """Set short-lived access and week-long rotating refresh cookies."""
    response.set_cookie(
        key=SESSION_COOKIE,
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/auth",
        max_age=AUTH_SESSION_MAX_DAYS * 24 * 60 * 60,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite=COOKIE_SAMESITE,
    )
    response.delete_cookie(
        key=REFRESH_COOKIE,
        path="/auth",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite=COOKIE_SAMESITE,
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
def google_login(request: Request, db: Session = Depends(get_db)):
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

    user, provisioning_error = _link_or_create_google_user(
        db, email, google_sub, claims, request
    )
    if provisioning_error:
        return _login_error_redirect(provisioning_error)

    # A fresh Google login replaces the current browser session.
    revoke_token_session(db, request.cookies.get(SESSION_COOKIE))
    revoke_refresh_session(db, request.cookies.get(REFRESH_COOKIE))
    access_token, refresh_token = create_user_session(db, user)
    db.commit()

    response = RedirectResponse(
        url=f"{FRONTEND_URL}/",
        status_code=303,
    )

    _set_session_cookies(response, access_token, refresh_token)
    response.headers["Cache-Control"] = "no-store"
    _clear_state_cookie(response)

    return response


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)):
    """Revoke the server-side session and clear the browser cookies."""
    revoke_token_session(db, request.cookies.get(SESSION_COOKIE))
    revoke_refresh_session(db, request.cookies.get(REFRESH_COOKIE))
    db.commit()
    response = Response(status_code=204)
    _clear_auth_cookies(response)
    _clear_state_cookie(response)

    return response


@router.post("/signup")
def signup(body: SignupRequest):
    """Keep the old endpoint explicit while all employee signup uses Google."""
    raise HTTPException(
        status_code=403,
        detail="Password signup is disabled. Continue with your verified company Google account.",
    )


@router.post("/login")
def login(
    body: LoginRequest,
):
    """Disable the old shared password login path."""
    raise HTTPException(
        status_code=403,
        detail="Employee sign-in uses Google. Administrators must sign in at /admin.",
    )


@router.post("/admin/login")
def admin_password_login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Authenticate an administrator with the password provisioned for that account."""
    email = str(body.email).strip().lower()
    check_email_domain(email)
    user = db.query(User).filter(User.email == email).first()

    # Use the same response for unknown users, non-admins, and bad passwords.
    if (
        user is None
        or user.role != "admin"
        or not verify_password(body.password, user.password_hash)
    ):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This administrator account is inactive.")

    revoke_token_session(db, request.cookies.get(SESSION_COOKIE))
    revoke_refresh_session(db, request.cookies.get(REFRESH_COOKIE))
    access_token, refresh_token = create_user_session(db, user)
    audit(
        db,
        user.id,
        "admin_password_login",
        "auth",
        "Administrator password sign-in",
        client_info(request),
    )
    db.commit()
    _set_session_cookies(response, access_token, refresh_token)
    response.headers["Cache-Control"] = "no-store"
    return user_full(user)


@router.post("/refresh", status_code=204)
def refresh_session(
    request: Request,
    db: Session = Depends(get_db),
):
    """Rotate the one-time refresh token and issue a fresh short-lived access token."""
    access_token, refresh_token, error = rotate_refresh_token(
        db, request.cookies.get(REFRESH_COOKIE)
    )
    if error:
        if error in {"refresh_token_reused", "account_unavailable"}:
            # Persist replay-triggered revocation before returning an error.
            db.commit()
        else:
            db.rollback()
        response = JSONResponse(
            status_code=401,
            content={"detail": "Session expired. Continue with Google to sign in again."},
            headers={"Cache-Control": "no-store"},
        )
        _clear_auth_cookies(response)
        return response

    db.commit()
    response = Response(status_code=204)
    _set_session_cookies(response, access_token, refresh_token)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    """Return the currently authenticated HRMS user."""
    return user_full(user)


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
                "Only administrators can use application passwords. "
                "Sign in with your verified company Google account."
            ),
        )

    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect",
        )

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    current_session_id = session_id_from_token(request.cookies.get(SESSION_COOKIE))
    revoke_user_sessions(db, user.id, except_session_id=current_session_id)

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
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only administrators can set an account password.",
        )

    if not user.must_change_password:
        raise HTTPException(
            status_code=400,
            detail="Use change-password with your current password instead",
        )

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    current_session_id = session_id_from_token(request.cookies.get(SESSION_COOKIE))
    revoke_user_sessions(db, user.id, except_session_id=current_session_id)

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
