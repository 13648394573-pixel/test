"""Allow persisted local runner results without changing historical sources.

Revision ID: 20261012_0022
Revises: 20260918_0021
"""

from alembic import op
import sqlalchemy as sa


revision = '20261012_0022'
down_revision = '20260918_0021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('run_results') as batch:
        batch.drop_constraint('ck_run_results_result_source', type_='check')
        batch.create_check_constraint('ck_run_results_result_source',
            "result_source IN ('MANUAL','RULE_ENGINE','LOCAL_RUNNER')")


def downgrade() -> None:
    used = op.get_bind().execute(sa.text(
        "SELECT COUNT(*) FROM run_results WHERE result_source = 'LOCAL_RUNNER'"
    )).scalar_one()
    if used:
        raise RuntimeError('Cannot downgrade while LOCAL_RUNNER results exist')
    with op.batch_alter_table('run_results') as batch:
        batch.drop_constraint('ck_run_results_result_source', type_='check')
        batch.create_check_constraint('ck_run_results_result_source',
            "result_source IN ('MANUAL','RULE_ENGINE')")
