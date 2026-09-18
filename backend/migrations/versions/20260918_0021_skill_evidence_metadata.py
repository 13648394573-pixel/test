"""add skill execution evidence metadata

Revision ID: 20260918_0021
Revises: 20260918_0020
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260918_0021"
down_revision: str | None = "20260918_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("evidences") as batch:
        batch.add_column(sa.Column("execution_session_id", sa.String(36)))
        batch.add_column(sa.Column("step_ref", sa.String(100)))
        batch.add_column(sa.Column("capture_method", sa.String(30)))
        batch.add_column(
            sa.Column("redacted", sa.Boolean(), nullable=False, server_default="0")
        )
        batch.create_foreign_key(
            "fk_evidences_execution_session",
            "execution_sessions",
            ["execution_session_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_evidences_execution_session_id",
        "evidences",
        ["execution_session_id"],
    )
    op.create_index(
        "ix_evidences_execution_session_step",
        "evidences",
        ["execution_session_id", "step_ref"],
    )

    with op.batch_alter_table("operator_interactions") as batch:
        batch.add_column(
            sa.Column(
                "interaction_type",
                sa.String(30),
                nullable=False,
                server_default="INSTRUCTION",
            )
        )
        batch.add_column(
            sa.Column(
                "risk_level", sa.String(20), nullable=False, server_default="LOW"
            )
        )
        batch.add_column(
            sa.Column("options_json", sa.JSON(), nullable=False, server_default="[]")
        )
        batch.add_column(sa.Column("impact_preview", sa.JSON()))
        batch.add_column(sa.Column("response_json", sa.JSON()))
        batch.create_check_constraint(
            "ck_operator_interactions_type",
            "interaction_type IN ('CONFIRMATION','INSTRUCTION','SELECTION','EVIDENCE')",
        )
        batch.create_check_constraint(
            "ck_operator_interactions_risk_level",
            "risk_level IN ('LOW','MEDIUM','HIGH')",
        )


def downgrade() -> None:
    connection = op.get_bind()
    used_evidence_metadata = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM evidences "
            "WHERE execution_session_id IS NOT NULL "
            "OR step_ref IS NOT NULL OR capture_method IS NOT NULL"
        )
    ).scalar_one()
    used_interaction_response = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM operator_interactions WHERE response_json IS NOT NULL"
        )
    ).scalar_one()
    if used_evidence_metadata or used_interaction_response:
        raise RuntimeError("Cannot downgrade while skill execution metadata is in use")

    with op.batch_alter_table("operator_interactions") as batch:
        batch.drop_constraint("ck_operator_interactions_risk_level", type_="check")
        batch.drop_constraint("ck_operator_interactions_type", type_="check")
        batch.drop_column("response_json")
        batch.drop_column("impact_preview")
        batch.drop_column("options_json")
        batch.drop_column("risk_level")
        batch.drop_column("interaction_type")

    op.drop_index("ix_evidences_execution_session_step", table_name="evidences")
    op.drop_index("ix_evidences_execution_session_id", table_name="evidences")
    with op.batch_alter_table("evidences") as batch:
        batch.drop_constraint("fk_evidences_execution_session", type_="foreignkey")
        batch.drop_column("redacted")
        batch.drop_column("capture_method")
        batch.drop_column("step_ref")
        batch.drop_column("execution_session_id")
