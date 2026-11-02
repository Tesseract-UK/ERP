"""Store check-in and check-out GPS accuracy and office distance.

Revision ID: f74c0b19d2a1
Revises: a41e9d20b6f3
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f74c0b19d2a1"
down_revision: Union[str, None] = "a41e9d20b6f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMNS = (
    "location_accuracy_meters",
    "distance_from_office_meters",
    "checkout_latitude",
    "checkout_longitude",
    "checkout_accuracy_meters",
    "checkout_distance_from_office_meters",
)


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("attendance")}
    for column in COLUMNS:
        if column not in existing:
            op.add_column("attendance", sa.Column(column, sa.Float(), nullable=True))


def downgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("attendance")}
    for column in reversed(COLUMNS):
        if column in existing:
            op.drop_column("attendance", column)
