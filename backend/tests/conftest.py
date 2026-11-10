"""Test harness: a throwaway SQLite database and Bearer-token clients per role.

Environment must be set before the app is imported, because config and the
engine are created at import time.
"""
import os
import sys
import tempfile
from datetime import date, timedelta

_DB_DIR = tempfile.mkdtemp(prefix="hrms-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_DIR}/test.db"
os.environ["APP_ENV"] = "test"
os.environ["EMAIL_BACKEND"] = "console"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-123456"
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import mailer  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import EmployeeLeavePolicy, LeavePolicy, User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.session_service import create_user_session  # noqa: E402


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for leave_type, allocation in (("casual", 12), ("sick", 12), ("earned", 15), ("wfh", 24)):
        session.add(LeavePolicy(leave_type=leave_type, annual_allocation=allocation))
    session.commit()
    yield session
    session.close()


@pytest.fixture()
def sent_emails(monkeypatch):
    """Capture emails synchronously instead of handing them to the thread pool."""
    sent = []
    monkeypatch.setattr(mailer._executor, "submit", lambda fn, *args: sent.append(args))
    return sent


class Org:
    """admin ← manager ← (alice, bob); hr ← admin; pending has no manager."""

    def __init__(self, db):
        self.db = db
        self.admin = self._user("admin", "admin")
        self.admin2 = self._user("admin2", "admin")
        self.hr = self._user("hr", "hr", manager=self.admin)
        self.manager = self._user("manager", "manager", manager=self.admin)
        self.other_manager = self._user("othermgr", "manager", manager=self.admin)
        self.alice = self._user("alice", "employee", manager=self.manager)
        self.bob = self._user("bob", "employee", manager=self.manager)
        self.carol = self._user("carol", "employee", manager=self.other_manager)
        self.pending = self._user("pending", "employee", manager=None)
        # Balances start at 0 until HR enters them; give the working
        # employees what HR normally would.
        for person in (self.hr, self.manager, self.other_manager, self.alice, self.bob, self.carol):
            self.allocate(person, casual=12, sick=10, wfh=24)
        db.commit()

    def allocate(self, user, **allocations):
        for leave_type, value in allocations.items():
            self.db.add(EmployeeLeavePolicy(user_id=user.id, leave_type=leave_type,
                                            annual_allocation=value))
        self.db.flush()

    def _user(self, name, role, manager=None):
        user = User(employee_code=f"T-{name}", email=f"{name}@tesseractuk.in",
                    full_name=name.title(), role=role, password_hash=hash_password("x" * 12),
                    manager_id=manager.id if manager else None, is_active=True,
                    profile_completed=manager is not None or role == "admin")
        self.db.add(user)
        self.db.flush()
        return user

    def client(self, user):
        access, _refresh = create_user_session(self.db, user)
        self.db.commit()
        client = TestClient(app)
        client.headers["Authorization"] = f"Bearer {access}"
        return client


@pytest.fixture()
def org(db):
    return Org(db)


def next_weekday(offset_days=7):
    d = date.today() + timedelta(days=offset_days)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d
