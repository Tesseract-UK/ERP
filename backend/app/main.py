"""HRMS API entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS
from .database import Base, engine
from .routers import (
    admin, approvals, attendance, auth, dashboard, hr, leaves, notifications,
    profile, regularization, team, wfh,
)

app = FastAPI(title="Tesseract HRMS API", version="1.0.0",
              docs_url="/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple create_all keeps the deployment story light; switch to Alembic
# migrations when the schema starts evolving in production.
Base.metadata.create_all(bind=engine)


def _ensure_new_columns():
    """Additive mini-migration for databases created before newer columns."""
    from sqlalchemy import inspect, text
    existing = {c["name"] for c in inspect(engine).get_columns("users")}
    with engine.begin() as conn:
        if "must_change_password" not in existing:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT FALSE"))
            conn.execute(text("UPDATE users SET must_change_password = FALSE"))
        if "profile_completed" not in existing:
            # Accounts predating the onboarding feature are treated as complete.
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN profile_completed BOOLEAN DEFAULT TRUE"))
            conn.execute(text("UPDATE users SET profile_completed = TRUE"))


_ensure_new_columns()

for router in (auth.router, dashboard.router, attendance.router, leaves.router,
               wfh.router, regularization.router, approvals.router, team.router,
               hr.router, admin.router, notifications.router, profile.router):
    app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
