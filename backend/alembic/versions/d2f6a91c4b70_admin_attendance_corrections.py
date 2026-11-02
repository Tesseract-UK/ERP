"""Store audited Admin attendance corrections separately from punch data.

Revision ID: d2f6a91c4b70
Revises: c8e2b41f6a30
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2f6a91c4b70"
down_revision: Union[str, None] = "c8e2b41f6a30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("attendance")}
    columns = (
        ("status_override", sa.String(length=20)),
        ("status_override_reason", sa.Text()),
        ("status_override_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_attendance_status_override_by_id_users")),
        ("status_override_at", sa.DateTime()),
    )
    with op.batch_alter_table("attendance") as batch:
        for item in columns:
            name, column_type, *constraints = item
            if name not in existing:
                batch.add_column(sa.Column(name, column_type, *constraints, nullable=True))


def downgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("attendance")}
    with op.batch_alter_table("attendance") as batch:
        for name in ("status_override_at", "status_override_by_id", "status_override_reason", "status_override"):
            if name in existing:
                batch.drop_column(name)
