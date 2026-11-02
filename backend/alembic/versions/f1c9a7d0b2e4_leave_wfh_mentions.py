"""Add optional colleague mentions to leave and WFH requests."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1c9a7d0b2e4"
down_revision: Union[str, None] = "e55c9a8b2d11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in ("leave_requests", "wfh_requests", "regularization_requests"):
        if table not in inspector.get_table_names():
            continue
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "mentions_json" not in columns:
            op.add_column(
                table,
                sa.Column("mentions_json", sa.Text(), nullable=False, server_default="[]"),
            )
            columns.add("mentions_json")
        if "manager_decided_by_id" not in columns:
            op.add_column(
                table,
                sa.Column("manager_decided_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in ("regularization_requests", "wfh_requests", "leave_requests"):
        if table in inspector.get_table_names():
            columns = {column["name"] for column in inspector.get_columns(table)}
            if "mentions_json" in columns:
                op.drop_column(table, "mentions_json")
            if "manager_decided_by_id" in columns:
                op.drop_column(table, "manager_decided_by_id")
