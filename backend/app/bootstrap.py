"""Make a brand-new (empty) production database usable. Runs at startup.

* Creates the standard leave-policy template rows if none exist.
* Creates the first Admin from INITIAL_ADMIN_EMAIL / INITIAL_ADMIN_PASSWORD /
  INITIAL_ADMIN_NAME when the database has no active Admin yet. Render's free
  tier has no shell, so this is the only way to get the first sign-in.

Never creates demo users (that is `python -m app.seed`, for local dev only).
Once an Admin exists, the INITIAL_ADMIN_* variables are ignored — remove them
from the environment after the first deploy.
"""
import logging
import os

from sqlalchemy.orm import Session

from .database import engine
from .models import LeavePolicy, User
from .security import hash_password
from .utils import check_email_domain

log = logging.getLogger("hrms.bootstrap")

DEFAULT_POLICIES = {
    "casual": 12, "sick": 10, "earned": 15, "unpaid": 0, "maternity": 182,
    "paternity": 15, "optional_holiday": 2, "wfh": 24,
}


def _ensure_policy_template(db: Session) -> None:
    have = {p.leave_type for p in db.query(LeavePolicy).all()}
    for leave_type, allocation in DEFAULT_POLICIES.items():
        if leave_type not in have:
            db.add(LeavePolicy(leave_type=leave_type, annual_allocation=allocation))


def _next_employee_code(db: Session) -> str:
    n = db.query(User).count() + 1
    while db.query(User.id).filter(User.employee_code == f"EMP{n:04d}").first():
        n += 1
    return f"EMP{n:04d}"


def _ensure_first_admin(db: Session) -> None:
    if db.query(User.id).filter(User.role == "admin", User.is_active.is_(True)).first():
        return
    email = os.getenv("INITIAL_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("INITIAL_ADMIN_PASSWORD", "")
    name = os.getenv("INITIAL_ADMIN_NAME", "").strip() or "Administrator"
    if not email or not password:
        log.warning("No active Admin exists. Set INITIAL_ADMIN_EMAIL and "
                    "INITIAL_ADMIN_PASSWORD to create the first one.")
        return
    if len(password) < 12:
        raise RuntimeError("INITIAL_ADMIN_PASSWORD must be at least 12 characters")
    check_email_domain(email)

    existing = db.query(User).filter(User.email == email).first()
    if existing:  # e.g. they signed in with Google first: promote them.
        existing.role, existing.manager_id, existing.is_active = "admin", None, True
        existing.password_hash = hash_password(password)
        existing.profile_completed = True
    else:
        db.add(User(employee_code=_next_employee_code(db), email=email, full_name=name,
                    role="admin", password_hash=hash_password(password),
                    is_active=True, profile_completed=True))
    log.warning("Created first Admin %s. Remove INITIAL_ADMIN_* from the environment now.", email)


def bootstrap() -> None:
    with Session(engine) as db:
        _ensure_policy_template(db)
        _ensure_first_admin(db)
        db.commit()
