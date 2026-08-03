"""Shared FastAPI dependencies: authentication and role-based authorization."""
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Account not found or deactivated")
    return user


def require_roles(*roles: str):
    """Dependency factory: allow only the given roles (admin always allowed)."""
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role != "admin" and user.role not in roles:
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action")
        return user
    return checker


require_manager = require_roles("manager", "hr")
require_hr = require_roles("hr")
require_admin = require_roles()  # admin only


def client_info(request: Request) -> dict:
    """Extract IP and a coarse browser/OS/device summary from the request."""
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "")
    ip = ip.split(",")[0].strip()
    ua = request.headers.get("user-agent", "")

    browser = "Unknown"
    for name, token in [("Edge", "Edg/"), ("Opera", "OPR/"), ("Chrome", "Chrome/"),
                        ("Safari", "Safari/"), ("Firefox", "Firefox/")]:
        if token in ua:
            browser = name
            break

    os_name = "Unknown"
    for name, token in [("Windows", "Windows"), ("macOS", "Mac OS X"), ("Android", "Android"),
                        ("iOS", "iPhone"), ("iOS", "iPad"), ("Linux", "Linux")]:
        if token in ua:
            os_name = name
            break

    device = "Mobile" if any(t in ua for t in ("Mobile", "Android", "iPhone")) else "Desktop"
    return {"ip": ip, "browser": browser, "os": os_name, "device": device, "user_agent": ua[:255]}
