"""restore V1 project planning metadata

Revision ID: 20260918_0017
Revises: 20260918_0016
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260918_0017"
down_revision: str | None = "20260918_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("test_projects") as batch:
        batch.add_column(sa.Column("project_code", sa.String(40)))
        batch.add_column(sa.Column("requirement", sa.Text()))
        batch.add_column(sa.Column("target_version", sa.String(100)))
        batch.add_column(sa.Column("scope", sa.Text()))
        batch.add_column(sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"))
        batch.add_column(sa.Column("planned_start_date", sa.Date()))
        batch.add_column(sa.Column("planned_end_date", sa.Date()))
        batch.create_check_constraint("ck_test_projects_status", "status IN ('DRAFT','ACTIVE','COMPLETED','ON_HOLD','CANCELLED')")
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id FROM test_projects ORDER BY created_at, id")).all()
    for sequence, row in enumerate(rows, start=1):
        connection.execute(
            sa.text("UPDATE test_projects SET project_code=:code WHERE id=:id"),
            {"code": f"LEGACY-{sequence:06d}", "id": row.id},
        )
    with op.batch_alter_table("test_projects") as batch:
        batch.alter_column("project_code", existing_type=sa.String(40), nullable=False)
        batch.create_unique_constraint("uq_test_projects_project_code", ["project_code"])


def downgrade() -> None:
    with op.batch_alter_table("test_projects") as batch:
        batch.drop_constraint("uq_test_projects_project_code", type_="unique")
        batch.drop_constraint("ck_test_projects_status", type_="check")
        for column in (
            "planned_end_date", "planned_start_date", "status", "scope",
            "target_version", "requirement", "project_code",
        ):
            batch.drop_column(column)
