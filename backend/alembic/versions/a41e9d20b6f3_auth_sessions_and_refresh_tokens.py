"""Add database-backed auth sessions and refresh tokens.

Revision ID: a41e9d20b6f3
Revises: 8ef86dc4383d
Create Date: 2026-10-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a41e9d20b6f3"
down_revision: Union[str, None] = "8ef86dc4383d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # app.main currently uses metadata.create_all at startup. These guards
    # also let Alembic safely adopt a database after that startup path ran.
    if "auth_sessions" not in tables:
        op.create_table(
            "auth_sessions",
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("session_id"),
        )
        op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
        op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])

    if "auth_refresh_tokens" not in tables:
        op.create_table(
            "auth_refresh_tokens",
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("consumed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["session_id"], ["auth_sessions.session_id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("token_hash"),
        )
        op.create_index(
            "ix_auth_refresh_tokens_session_id", "auth_refresh_tokens", ["session_id"]
        )

def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "auth_refresh_tokens" in tables:
        op.drop_table("auth_refresh_tokens")
    if "auth_sessions" in tables:
        op.drop_table("auth_sessions")
