# V1 Empty Database Migration Validation

## 验证信息

| 项目 | 记录 |
|---|---|
| 日期 | 2026-08-08 |
| 分支/基线 | `main` / `5e362687a3a89ee5b4336c9a1db68105858ea875` |
| 目标数据库 | `data/release-prep-empty-20260808.db`（Git忽略，不提交） |
| 初始状态 | 0字节空SQLite文件 |
| 目标Revision | `20260730_0007` |

## 方法

使用`alembic.config.Config`加载`backend/alembic.ini`，再通过`set_main_option('sqlalchemy.url', ...)`把目标显式指向独立空数据库，执行`command.upgrade(config, 'head')`。

## 迁移链

```text
20260729_0001 devices
→ 20260729_0002 test case library
→ 20260729_0003 test execution
→ 20260730_0004 defect/regression
→ 20260730_0005 result integrity/evidence
→ 20260730_0006 environment snapshot
→ 20260730_0007 report/archive
```

## 验证结果

| 检查项 | 结果 |
|---|---|
| Alembic current | `20260730_0007 (head)` |
| 表数量 | 16（含`alembic_version`） |
| 业务表初始记录 | 全部0条 |
| `PRAGMA quick_check` | `ok` |
| `PRAGMA foreign_key_check` | 0条违规 |
| 最终判定 | PASS |

生成表：`devices`、`test_cases`、`case_steps`、`test_projects`、`project_case_selections`、`test_runs`、`run_results`、`environment_profiles`、`environment_parameters`、`run_environment_snapshots`、`evidences`、`defects`、`regressions`、`reports`、`archives`和`alembic_version`。

## 发现与技术债

直接设置`TEST_WORKBENCH_DATABASE_URL`后运行Alembic CLI不会切换迁移目标，因为`backend/migrations/env.py`只读取`backend/alembic.ini`中的`sqlalchemy.url`。首次尝试因此仍指向默认数据库，独立目标保持0字节；未产生结构污染。

本阶段不修改迁移代码。README和DATABASE文档已明确：默认CLI用于默认数据库，自定义数据库必须显式覆盖Alembic Config URL。

## 结论

当前7个迁移可以从空数据库连续升级到head，结构、外键和SQLite完整性验证通过。空数据库迁移验收：`PASS`。
