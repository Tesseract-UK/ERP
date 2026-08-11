"""One-off: create (or promote) a single real admin account — for
production, where the full demo seed data (app/seed.py) isn't wanted.

Run in the Render Shell tab:  python -m app.create_admin

Prompts for name, email and password interactively — the password input
is hidden and never appears in shell history or logs. Safe to re-run: if
the email already exists, it just promotes that account to admin and
updates the password instead of erroring.
"""
import getpass

from fastapi import HTTPException

from .database import Base, SessionLocal, engine
from .models import User
from .security import hash_password
from .utils import check_email_domain, generate_employee_code


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        full_name = input("Full name: ").strip()
        email = input("Email (must be on the allowed company domain): ").strip().lower()
        try:
            check_email_domain(email)
        except HTTPException as e:
            print(f"Error: {e.detail}")
            return

        while True:
            password = getpass.getpass("Password (min 8 characters, hidden): ")
            if len(password) < 8:
                print("Too short — try again.")
                continue
            if password != getpass.getpass("Confirm password: "):
                print("Passwords didn't match — try again.")
                continue
            break

        existing = db.query(User).filter(User.email == email).first()
        if existing:
            existing.role = "admin"
            existing.password_hash = hash_password(password)
            existing.is_active = True
            existing.must_change_password = False
            db.commit()
            print(f"\nExisting account promoted to admin: {email}")
        else:
            user = User(
                employee_code=generate_employee_code(db), email=email,
                full_name=full_name, role="admin",
                password_hash=hash_password(password),
                profile_completed=True, must_change_password=False,
            )
            db.add(user)
            db.commit()
            print(f"\nAdmin account created: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
