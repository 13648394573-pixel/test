"""verify the V1 baseline before adding V2 domains

Revision ID: 20260918_0011
Revises: 20260811_0010
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260918_0011"
down_revision: str | None = "20260811_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    required_tables = {
        "devices",
        "test_cases",
        "test_projects",
        "test_runs",
        "run_results",
        "evidences",
        "evidence_run_result_links",
        "defects",
        "regressions",
        "reports",
        "archives",
    }
    missing_tables = required_tables - set(inspector.get_table_names())
    if missing_tables:
        raise RuntimeError(
            "V1 baseline is incomplete; missing tables: "
            + ", ".join(sorted(missing_tables))
        )
    run_columns = {column["name"] for column in inspector.get_columns("test_runs")}
    if "run_no" not in run_columns:
        raise RuntimeError("V1 baseline is incomplete; test_runs.run_no is missing")


def downgrade() -> None:
    pass
