"""Shared FastAPI dependencies: authentication and role-based authorization."""

from fastapi import (
    Cookie,
    Depends,
    HTTPException,
    Request,
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import decode_token


bearer = HTTPBearer(auto_error=False)


def _get_user_from_token(token: str, db: Session) -> User | None:
    """Decode an HRMS JWT and return its active database user."""

    payload = decode_token(token)

    if not payload:
        return None

    subject = payload.get("sub")

    if subject is None:
        return None

    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        return None

    user = db.get(User, user_id)

    if user is None or not user.is_active:
        return None

    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session_token: str | None = Cookie(
        default=None,
        alias="hrms_session",
    ),
    db: Session = Depends(get_db),
) -> User:
    """
    Authenticate an active HRMS user using either:
    1. Authorization: Bearer <HRMS JWT>
    2. The HttpOnly hrms_session cookie.

    Both methods support employee, manager, HR and admin accounts.
    Authorization restrictions are enforced separately by require_roles.
    """

    # Prefer an explicitly supplied Bearer token.
    if credentials is not None:
        user = _get_user_from_token(credentials.credentials, db)

        if user is not None:
            return user

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Otherwise, authenticate through the Google SSO session cookie.
    if session_token:
        user = _get_user_from_token(session_token, db)

        if user is not None:
            return user

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
        )

    raise HTTPException(
        status_code=401,
        detail="Not authenticated or session expired",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_roles(*roles: str):
    """Allow the specified roles; admins retain existing elevated access."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role != "admin" and user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to perform this action",
            )

        return user

    return checker


require_manager = require_roles("manager", "hr")
require_hr = require_roles("hr")
require_admin = require_roles()


def client_info(request: Request) -> dict:
    """Extract IP and a coarse browser/OS/device summary."""

    ip = request.headers.get(
        "x-forwarded-for",
        request.client.host if request.client else "",
    )
    ip = ip.split(",")[0].strip()
    ua = request.headers.get("user-agent", "")

    browser = "Unknown"

    for name, token in [
        ("Edge", "Edg/"),
        ("Opera", "OPR/"),
        ("Chrome", "Chrome/"),
        ("Safari", "Safari/"),
        ("Firefox", "Firefox/"),
    ]:
        if token in ua:
            browser = name
            break

    os_name = "Unknown"

    for name, token in [
        ("Windows", "Windows"),
        ("macOS", "Mac OS X"),
        ("Android", "Android"),
        ("iOS", "iPhone"),
        ("iOS", "iPad"),
        ("Linux", "Linux"),
    ]:
        if token in ua:
            os_name = name
            break

    device = (
        "Mobile"
        if any(token in ua for token in ("Mobile", "Android", "iPhone"))
        else "Desktop"
    )

    return {
        "ip": ip,
        "browser": browser,
        "os": os_name,
        "device": device,
        "user_agent": ua[:255],
    }