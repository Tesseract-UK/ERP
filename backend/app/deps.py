"""Shared FastAPI dependencies: authentication and role-based authorization."""
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from .clerk import sync_clerk_user
from .config import CLERK_JWKS_URL
from .database import get_db
from .models import User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)
# Cached JWKS client: fetches Clerk's public signing keys once and reuses
# them (PyJWKClient refreshes automatically if a `kid` isn't found yet).
_jwks_client = PyJWKClient(CLERK_JWKS_URL, cache_keys=True) if CLERK_JWKS_URL else None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = credentials.credentials

    # Primary path: Clerk session token (RS256, verified against Clerk's JWKS).
    if _jwks_client is not None:
        try:
            signing_key = _jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(token, signing_key.key,
                                algorithms=["RS256"], options={"verify_aud": False})
            clerk_user_id = claims.get("sub")
            if clerk_user_id:
                user = db.query(User).filter(User.clerk_user_id == clerk_user_id).first()
                if user is None:
                    user = sync_clerk_user(db, clerk_user_id)
                if not user.is_active:
                    raise HTTPException(status_code=403, detail="Your account has been deactivated. Contact HR.")
                return user
        except HTTPException:
            raise
        except Exception:
            pass  # not a valid Clerk session token — fall through to the admin fallback below

    # Break-glass fallback: the legacy email+password JWT, admin accounts
    # only. Everyone else must use Clerk. Keeps a working way in if Clerk
    # or Google sign-in is ever unavailable.
    payload = decode_token(token)
    if payload is not None:
        user = db.get(User, int(payload["sub"]))
        if user is not None and user.is_active and user.role == "admin":
            return user

    raise HTTPException(status_code=401, detail="Invalid or expired session")


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
