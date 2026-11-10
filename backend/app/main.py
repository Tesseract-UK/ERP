
"""HRMS API entrypoint."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text

from .config import CORS_ORIGINS
from .database import Base, engine
from .routers import (
    admin,
    approvals,
    attendance,
    auth,
    company_calendar,
    conversations,
    dashboard,
    employee_requests,
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


@app.middleware("http")
async def protect_browser_writes(request: Request, call_next):
    """Reject cross-site writes that could abuse the Google session cookie."""
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        has_session_cookie = bool(
            request.cookies.get("hrms_session")
            or request.cookies.get("hrms_refresh")
        )
        if origin and origin not in CORS_ORIGINS:
            return JSONResponse(
                status_code=403,
                content={"detail": "Request origin is not allowed"},
            )
        if has_session_cookie and origin not in CORS_ORIGINS:
            return JSONResponse(
                status_code=403,
                content={"detail": "Session write requests require an allowed origin"},
            )

    return await call_next(request)

# Invalidate sessions from the previous token format on the first startup
# after refresh-token support is added. Employee records are untouched.
tables_before_auth_upgrade = set(inspect(engine).get_table_names())
upgrade_legacy_sessions = (
    "auth_sessions" in tables_before_auth_upgrade
    and "auth_refresh_tokens" not in tables_before_auth_upgrade
)

# Create missing tables. Existing tables are updated by the additive
# migration below; create_all alone does not add columns to existing tables.
Base.metadata.create_all(bind=engine)

if upgrade_legacy_sessions:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE auth_sessions SET revoked_at = CURRENT_TIMESTAMP "
                "WHERE revoked_at IS NULL"
            )
        )


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

        attendance_columns = {
            column["name"] for column in inspect(engine).get_columns("attendance")
        }
        for column in (
            "location_accuracy_meters",
            "distance_from_office_meters",
            "checkout_latitude",
            "checkout_longitude",
            "checkout_accuracy_meters",
            "checkout_distance_from_office_meters",
        ):
            if column not in attendance_columns:
                conn.execute(text(f"ALTER TABLE attendance ADD COLUMN {column} FLOAT"))

        attendance_columns = {
            column["name"] for column in inspect(engine).get_columns("attendance")
        }
        correction_columns = {
            "status_override": "VARCHAR(20)",
            "status_override_reason": "TEXT",
            "status_override_by_id": "INTEGER REFERENCES users(id)",
            "status_override_at": "TIMESTAMP",
        }
        for name, ddl in correction_columns.items():
            if name not in attendance_columns:
                conn.execute(text(f"ALTER TABLE attendance ADD COLUMN {name} {ddl}"))

        # Staged approvals are additive so existing leave/WFH/regularization
        # records and their current decisions remain intact.
        for table in ("leave_requests", "wfh_requests", "regularization_requests"):
            columns = {column["name"] for column in inspect(engine).get_columns(table)}
            additions = {
                "approval_stage": "VARCHAR(20) NOT NULL DEFAULT 'pending_manager'",
                "manager_decided_at": "TIMESTAMP",
                "manager_decided_by_id": "INTEGER REFERENCES users(id)",
                "manager_comment": "TEXT",
                "hr_decided_at": "TIMESTAMP",
                "hr_comment": "TEXT",
            }
            for name, ddl in additions.items():
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
            conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS ix_{table}_approval_stage "
                f"ON {table} (approval_stage)"
            ))

        additive_columns = {
            "leave_requests": {"mentions_json": "TEXT NOT NULL DEFAULT '[]'"},
            "wfh_requests": {"mentions_json": "TEXT NOT NULL DEFAULT '[]'"},
            "regularization_requests": {"mentions_json": "TEXT NOT NULL DEFAULT '[]'"},
            "notifications": {
                "actor_id": "INTEGER REFERENCES users(id)",
                "entity_type": "VARCHAR(40)",
                "entity_id": "INTEGER",
            },
        }
        for table, additions in additive_columns.items():
            columns = {column["name"] for column in inspect(engine).get_columns(table)}
            for name, ddl in additions.items():
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


_ensure_new_columns()


def _backfill_conversation_participants():
    """People tagged before conversations existed become thread participants."""
    import json
    from sqlalchemy.orm import Session as _Session
    from .models import (LeaveRequest, RegularizationRequest, RequestParticipant,
                         WFHRequest)
    with _Session(engine) as db:
        existing = {(p.kind, p.request_id, p.user_id) for p in db.query(RequestParticipant).all()}
        for kind, model in (("leave", LeaveRequest), ("wfh", WFHRequest),
                            ("regularization", RegularizationRequest)):
            for req in db.query(model).filter(model.mentions_json.notin_(["[]", ""])).all():
                try:
                    ids = json.loads(req.mentions_json or "[]")
                except (TypeError, ValueError):
                    continue
                for user_id in ids:
                    if isinstance(user_id, int) and (kind, req.id, user_id) not in existing:
                        db.add(RequestParticipant(kind=kind, request_id=req.id,
                                                  user_id=user_id, added_by_id=req.user_id))
                        existing.add((kind, req.id, user_id))
        db.commit()


_backfill_conversation_participants()

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
    employee_requests.router,
    notifications.router,
    profile.router,
    conversations.router,
    company_calendar.router,
):
    app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
