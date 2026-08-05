"""Links Clerk-authenticated identities to local User rows.

Verification of the session token itself happens in deps.py (JWKS
signature check). Once we trust the token's `sub` claim, this module fetches
the Clerk profile once per never-seen-before identity, enforces the company
email-domain restriction, and either links it to an existing HR-provisioned
employee (matched by email) or provisions a new self-service account.
"""
import secrets

import httpx
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import ALLOWED_EMAIL_DOMAINS, CLERK_SECRET_KEY
from .models import User
from .security import hash_password
from .utils import generate_employee_code


def _fetch_clerk_profile(clerk_user_id: str) -> dict:
    try:
        resp = httpx.get(
            f"https://api.clerk.com/v1/users/{clerk_user_id}",
            headers={"Authorization": f"Bearer {CLERK_SECRET_KEY}"},
            timeout=10,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Could not reach Clerk to verify your session")
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Could not verify your Clerk session")
    return resp.json()


def sync_clerk_user(db: Session, clerk_user_id: str) -> User:
    """Called the first time a given Clerk identity is seen. Links or
    creates the corresponding local User row and returns it."""
    profile = _fetch_clerk_profile(clerk_user_id)
    primary_id = profile.get("primary_email_address_id")
    email = next(
        (e["email_address"] for e in profile.get("email_addresses", [])
         if e["id"] == primary_id),
        None,
    )
    if not email:
        raise HTTPException(status_code=400, detail="Your account has no verified email address")
    email = email.lower()

    if "*" not in ALLOWED_EMAIL_DOMAINS:
        domain = email.rsplit("@", 1)[-1]
        if domain not in ALLOWED_EMAIL_DOMAINS:
            allowed = " or ".join(f"@{d}" for d in ALLOWED_EMAIL_DOMAINS)
            raise HTTPException(
                status_code=403,
                detail=f"You need a {allowed} organization email address to sign up for Tesseract HRMS")

    user = db.query(User).filter(func.lower(User.email) == email).first()
    if user is not None:
        user.clerk_user_id = clerk_user_id
    else:
        full_name = " ".join(filter(None, [profile.get("first_name"), profile.get("last_name")])) or email
        user = User(
            clerk_user_id=clerk_user_id, email=email, full_name=full_name,
            employee_code=generate_employee_code(db),
            # Unusable random hash: this account only ever authenticates via
            # Clerk, but password_hash stays NOT NULL for existing rows.
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role="employee", profile_completed=False,
        )
        db.add(user)
    db.commit()
    db.refresh(user)
    return user
