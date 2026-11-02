"""Link actionable notifications and regularization mentions.

Revision ID: e55c9a8b2d11
Revises: d2f6a91c4b70
Create Date: 2026-11-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e55c9a8b2d11"
down_revision: Union[str, None] = "d2f6a91c4b70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "regularization_requests" in tables:
        columns = {column["name"] for column in inspector.get_columns("regularization_requests")}
        if "mentions_json" not in columns:
            op.add_column(
                "regularization_requests",
                sa.Column("mentions_json", sa.Text(), nullable=False, server_default="[]"),
            )

    if "notifications" in tables:
        columns = {column["name"] for column in inspector.get_columns("notifications")}
        if "actor_id" not in columns:
            op.add_column(
                "notifications",
                sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            )
        if "entity_type" not in columns:
            op.add_column("notifications", sa.Column("entity_type", sa.String(40), nullable=True))
        if "entity_id" not in columns:
            op.add_column("notifications", sa.Column("entity_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "notifications" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("notifications")}
        with op.batch_alter_table("notifications") as batch:
            for name in ("entity_id", "entity_type", "actor_id"):
                if name in columns:
                    batch.drop_column(name)
    if "regularization_requests" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("regularization_requests")}
        if "mentions_json" in columns:
            op.drop_column("regularization_requests", "mentions_json")
