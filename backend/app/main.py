
"""HRMS API entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from .config import CORS_ORIGINS
from .database import Base, engine
from .routers import (
    admin,
    approvals,
    attendance,
    auth,
    dashboard,
    hr,
    leaves,
    notifications,
    profile,
    regularization,
    team,
    wfh,
)

app = FastAPI(
    title="Tesseract HRMS API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create missing tables. Existing tables are updated by the additive
# migration below; create_all alone does not add columns to existing tables.
Base.metadata.create_all(bind=engine)


def _ensure_new_columns():
    """Add new columns to existing databases without deleting data."""
    existing = {
        column["name"]
        for column in inspect(engine).get_columns("users")
    }

    with engine.begin() as conn:
        if "must_change_password" not in existing:
            conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN must_change_password BOOLEAN DEFAULT FALSE"
                )
            )
            conn.execute(
                text(
                    "UPDATE users SET must_change_password = FALSE"
                )
            )

        if "profile_completed" not in existing:
            # Accounts predating onboarding are treated as complete.
            conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN profile_completed BOOLEAN DEFAULT TRUE"
                )
            )
            conn.execute(
                text(
                    "UPDATE users SET profile_completed = TRUE"
                )
            )

        if "clerk_user_id" not in existing:
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN clerk_user_id VARCHAR(64)"
                )
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "ix_users_clerk_user_id ON users (clerk_user_id)"
                )
            )

        if "google_sub" not in existing:
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN google_sub VARCHAR(255)"
                )
            )

        # Supports both new and existing databases.
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_users_google_sub ON users (google_sub)"
            )
        )


_ensure_new_columns()

for router in (
    auth.router,
    dashboard.router,
    attendance.router,
    leaves.router,
    wfh.router,
    regularization.router,
    approvals.router,
    team.router,
    hr.router,
    admin.router,
    notifications.router,
    profile.router,
):
    app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
