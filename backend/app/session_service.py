"""Creation, rotation, and revocation for HRMS access/refresh sessions."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from .config import ACCESS_TOKEN_EXPIRE_MINUTES, AUTH_SESSION_MAX_DAYS, SECRET_KEY
from .models import AuthRefreshToken, AuthSession, User
from .security import create_access_token, decode_token


def _refresh_hash(token: str) -> str:
    """Hash refresh secrets with a server-side key; raw refresh tokens are never stored."""
    return hmac.new(
        SECRET_KEY.encode("utf-8"), token.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _new_refresh_token(session_id: str) -> tuple[str, str]:
    token = f"{session_id}.{secrets.token_urlsafe(32)}"
    return token, _refresh_hash(token)


def create_user_session(db: Session, user: User) -> tuple[str, str]:
    """Create a seven-day server session and its first access/refresh tokens."""
    now = datetime.utcnow()
    expires_at = now + timedelta(days=AUTH_SESSION_MAX_DAYS)
    session_id = secrets.token_urlsafe(32)

    expired_sessions = select(AuthSession.session_id).where(
        or_(AuthSession.expires_at <= now, AuthSession.revoked_at.is_not(None))
    )
    db.query(AuthRefreshToken).filter(
        AuthRefreshToken.session_id.in_(expired_sessions)
    ).delete(synchronize_session=False)
    db.query(AuthSession).filter(
        or_(AuthSession.expires_at <= now, AuthSession.revoked_at.is_not(None))
    ).delete(
        synchronize_session=False
    )

    db.add(AuthSession(
        session_id=session_id,
        user_id=user.id,
        expires_at=expires_at,
    ))
    db.flush()

    refresh_token, refresh_hash = _new_refresh_token(session_id)
    db.add(AuthRefreshToken(token_hash=refresh_hash, session_id=session_id))
    access_token = create_access_token(user.id, user.role, session_id)
    return access_token, refresh_token


def rotate_refresh_token(
    db: Session, raw_token: str | None
) -> tuple[str | None, str | None, str | None]:
    """Consume one refresh token and issue its replacement exactly once.

    Returns access token, refresh token, and an error code. A replay of a known
    consumed token revokes the whole session; an unknown token cannot revoke a
    session merely by guessing its public session identifier.
    """
    if not raw_token or raw_token.count(".") != 1:
        return None, None, "invalid_refresh_token"

    session_id, verifier = raw_token.split(".", 1)
    if not session_id or not verifier:
        return None, None, "invalid_refresh_token"

    now = datetime.utcnow()
    session = (
        db.query(AuthSession)
        .filter(AuthSession.session_id == session_id)
        .with_for_update()
        .first()
    )
    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at <= now
    ):
        return None, None, "invalid_refresh_token"

    token_hash = _refresh_hash(raw_token)
    stored = (
        db.query(AuthRefreshToken)
        .filter(AuthRefreshToken.token_hash == token_hash)
        .with_for_update()
        .first()
    )
    if stored is None or stored.session_id != session_id:
        return None, None, "invalid_refresh_token"

    if stored.consumed_at is not None:
        session.revoked_at = now
        return None, None, "refresh_token_reused"

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        session.revoked_at = now
        return None, None, "account_unavailable"

    # Make consumption atomic even on databases (such as SQLite) that ignore
    # SELECT ... FOR UPDATE. Only one concurrent request can win this update.
    consumed = db.execute(
        update(AuthRefreshToken)
        .where(
            AuthRefreshToken.token_hash == token_hash,
            AuthRefreshToken.session_id == session_id,
            AuthRefreshToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    if consumed.rowcount != 1:
        session.revoked_at = now
        return None, None, "refresh_token_reused"

    next_refresh_token, next_refresh_hash = _new_refresh_token(session_id)
    db.add(AuthRefreshToken(
        token_hash=next_refresh_hash,
        session_id=session_id,
    ))
    next_access_token = create_access_token(user.id, user.role, session_id)
    return next_access_token, next_refresh_token, None


def revoke_token_session(db: Session, token: str | None) -> None:
    """Revoke the session referenced by a valid JWT, even if that JWT expired."""
    session_id = session_id_from_token(token, verify_exp=False)
    if session_id:
        session = db.get(AuthSession, session_id)
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.utcnow()


def revoke_refresh_session(db: Session, raw_token: str | None) -> None:
    """Revoke a session using its current or previously rotated refresh token."""
    if not raw_token or raw_token.count(".") != 1:
        return
    session_id, verifier = raw_token.split(".", 1)
    if not session_id or not verifier:
        return
    stored = db.get(AuthRefreshToken, _refresh_hash(raw_token))
    if stored is None or stored.session_id != session_id:
        return
    session = db.get(AuthSession, session_id)
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.utcnow()


def session_id_from_token(token: str | None, *, verify_exp: bool = True) -> str | None:
    if not token:
        return None
    payload = decode_token(token, verify_exp=verify_exp)
    session_id = payload.get("sid") if payload else None
    return session_id if isinstance(session_id, str) else None


def revoke_user_sessions(
    db: Session, user_id: int, *, except_session_id: str | None = None
) -> None:
    """Revoke active sessions after a security event, optionally keeping this one."""
    query = db.query(AuthSession).filter(
        AuthSession.user_id == user_id,
        AuthSession.revoked_at.is_(None),
    )
    if except_session_id:
        query = query.filter(AuthSession.session_id != except_session_id)
    query.update({AuthSession.revoked_at: datetime.utcnow()}, synchronize_session=False)
