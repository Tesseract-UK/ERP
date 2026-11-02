"""Add private employee service requests and participants.

Revision ID: b9ec7a2d4f61
Revises: f74c0b19d2a1
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9ec7a2d4f61"
down_revision: Union[str, None] = "f74c0b19d2a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "employee_requests" not in tables:
        op.create_table(
            "employee_requests",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("requester_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("category", sa.String(length=80), nullable=False),
            sa.Column("priority", sa.String(length=20), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("attachment_path", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["requester_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_employee_requests_requester_id", "employee_requests", ["requester_id"])
        op.create_index("ix_employee_requests_status", "employee_requests", ["status"])

    tables = set(sa.inspect(bind).get_table_names())
    if "employee_request_participants" not in tables:
        op.create_table(
            "employee_request_participants",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("request_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("added_by_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["request_id"], ["employee_requests.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["added_by_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("request_id", "user_id", name="uq_request_participant"),
        )
        op.create_index("ix_employee_request_participants_request_id", "employee_request_participants", ["request_id"])
        op.create_index("ix_employee_request_participants_user_id", "employee_request_participants", ["user_id"])

    tables = set(sa.inspect(bind).get_table_names())
    if "employee_request_messages" not in tables:
        op.create_table(
            "employee_request_messages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("request_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("message_type", sa.String(length=20), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["request_id"], ["employee_requests.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_employee_request_messages_request_id", "employee_request_messages", ["request_id"])
        op.create_index("ix_employee_request_messages_user_id", "employee_request_messages", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "employee_request_messages" in tables:
        op.drop_table("employee_request_messages")
    if "employee_request_participants" in tables:
        op.drop_table("employee_request_participants")
    if "employee_requests" in tables:
        op.drop_table("employee_requests")
