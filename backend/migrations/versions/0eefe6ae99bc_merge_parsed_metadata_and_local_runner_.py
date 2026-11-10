"""merge parsed_metadata and local_runner result source

合并两条并行的迁移分支：
- 20261029_0022（evidences.parsed_metadata，来自报告/证据线）
- 20261012_0022（run_results 的 result_source 允许 LOCAL_RUNNER，来自自动化执行线）

两者 down_revision 同为 20260918_0021，合并后出现双 head，故在同一父节点上收敛。
两条迁移改动的是不同表（evidences / run_results），无先后依赖，本节点无需数据操作。

Revision ID: 0eefe6ae99bc
Revises: 20261012_0022, 20261029_0022
Create Date: 2026-11-10 15:56:47.834099
"""
from typing import Sequence, Union


revision: str = "0eefe6ae99bc"
down_revision: Union[str, Sequence[str], None] = ("20261012_0022", "20261029_0022")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """两条父迁移互相独立，无汇总动作。"""


def downgrade() -> None:
    """拆回双 head 由 alembic 依据父节点自动处理，无汇总动作。"""
