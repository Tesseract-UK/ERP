"""Add manager then HR approval stages to employee requests."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "c8e2b41f6a30"
down_revision: Union[str, None] = "b9ec7a2d4f61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    for table in ("leave_requests", "wfh_requests", "regularization_requests"):
        if table not in tables:
            continue
        cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        additions = (
            ("approval_stage", sa.String(20), "pending_manager"),
            ("manager_decided_at", sa.DateTime(), None),
            ("manager_comment", sa.Text(), None),
            ("hr_decided_at", sa.DateTime(), None),
            ("hr_comment", sa.Text(), None),
        )
        for name, typ, default in additions:
            if name not in cols:
                op.add_column(table, sa.Column(name, typ, nullable=name != "approval_stage", server_default=sa.text("'pending_manager'") if default else None))
        index_name = f"ix_{table}_approval_stage"
        if index_name not in {i["name"] for i in sa.inspect(bind).get_indexes(table)}:
            op.create_index(index_name, table, ["approval_stage"])


def downgrade() -> None:
    for table in ("regularization_requests", "wfh_requests", "leave_requests"):
        if table not in sa.inspect(op.get_bind()).get_table_names():
            continue
        if f"ix_{table}_approval_stage" in {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}:
            op.drop_index(f"ix_{table}_approval_stage", table_name=table)
        cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
        for column in ("hr_comment", "hr_decided_at", "manager_comment", "manager_decided_at", "approval_stage"):
            if column in cols:
                op.drop_column(table, column)
