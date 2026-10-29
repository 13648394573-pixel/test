"""add evidence parsed metadata

Revision ID: 20261029_0022
Revises: 20260918_0021
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261029_0022"
down_revision: str | None = "20260918_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("evidences") as batch:
        batch.add_column(sa.Column("parsed_metadata", sa.Text()))


def downgrade() -> None:
    with op.batch_alter_table("evidences") as batch:
        batch.drop_column("parsed_metadata")
