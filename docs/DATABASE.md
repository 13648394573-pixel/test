# Test Workbench 数据库

## 引擎与连接

- 数据库：SQLite
- 默认URL：`sqlite:///./data/test_workbench.db`
- 应用配置：`TEST_WORKBENCH_DATABASE_URL`
- ORM：SQLAlchemy 2.x
- 迁移：Alembic
- SQLite外键：每个连接执行`PRAGMA foreign_keys=ON`

Session使用`autoflush=False`、`expire_on_commit=False`。业务事务由Repository/Service控制。

## 表与关系

空库迁移至head后共有20张表（含`alembic_version`）。

| 表 | 关键字段/规则 | 关系 |
|---|---|---|
| `devices` | UUID；`serial_number`唯一；设备类型、厂商、型号、版本 | 被Run以source id引用并生成快照 |
| `test_cases` | `case_code`唯一；P0–P3；enabled | 1:N `case_steps` |
| `case_steps` | `(test_case_id, step_number)`唯一；action、expected_result | 删除TestCase时级联 |
| `test_projects` | name、version、description | 1:N selections、runs |
| `project_case_selections` | `(project_id, case_source_id)`复合主键 | 项目删除时级联 |
| `test_runs` | device_snapshot JSON；status IN_PROGRESS/COMPLETED；version=1 | N:1 project；1:N results；1:1 environment snapshot |
| `run_results` | case_snapshot JSON；PASS/FAIL/BLOCKED/NULL；DRAFT/LOCKED | Run删除时级联；可关联Evidence/Defect/Regression |
| `environment_profiles` | name唯一；enabled | 1:N parameters |
| `environment_parameters` | profile内`param_key`唯一；display_order≥1 | Profile删除时级联 |
| `run_environment_snapshots` | 每个Run唯一；profile_snapshot JSON；version=1 | Run删除时级联 |
| `evidences` | 必须且只能属于RunResult或Defect之一；路径唯一；SHA256 | Owner删除时级联 |
| `defects` | defect_code唯一；source_result唯一；S1–S4；状态约束 | 来源Result RESTRICT；1:N regressions |
| `regressions` | `(defect_id, verification_result)`唯一；追加式 | Result RESTRICT；Defect删除时级联（API不提供删除） |
| `reports` | Run内版本唯一；snapshot JSON；HTML路径/hash/大小 | Project/Run删除RESTRICT；1:1 archive |
| `archives` | `report_id`唯一；manifest JSON；ZIP路径/hash/大小 | Report/Project删除RESTRICT |
| `diagnostic_sessions` | Ping策略快照；PENDING/RUNNING/COMPLETED/FAILED/INTERRUPTED | N:1 RunResult；活动Session唯一 |
| `diagnostic_attempts` | 分层、目标、丢包率、时延和原始输出；追加式 | N:1 Diagnostic Session |
| `diagnostic_attempt_evidences` | Attempt与Evidence复合主键 | Diagnostic/Evidence关联 |
| `focused_regression_runs` | `test_run_id`唯一；Defect Snapshot JSON；version=1 | TestRun/Defect/来源Result均RESTRICT |
| `alembic_version` | 当前revision | Alembic内部表 |

## 不变性规则

- `device_snapshot`、`case_snapshot`、`profile_snapshot`创建后不可修改。
- `snapshot_version`固定为1。
- RunResult从DRAFT单向进入LOCKED，不能解锁；LOCKED结果字段不可修改。
- Defect只能来源于LOCKED FAIL/BLOCKED Result，且一个Result最多一个Defect。
- Regression记录不可更新或删除。
- Evidence元数据不可更新，文件内容通过SHA256验证。
- Report和Archive记录不可更新或删除；文件hash不匹配时拒绝下载或归档。
- Focused Regression关联及Defect Snapshot不可更新或删除；每次回归必须产生新的TestRun。

## 迁移历史

| Revision | 内容 |
|---|---|
| `20260729_0001` | devices |
| `20260729_0002` | test_cases、case_steps |
| `20260729_0003` | projects、selections、runs、results和设备/用例快照 |
| `20260730_0004` | defects、regressions |
| `20260730_0005` | Result完整性字段、evidences、SQLite外键强化 |
| `20260730_0006` | environment profiles、parameters、Run环境快照 |
| `20260730_0007` | reports、archives |
| `20260808_0008` | diagnostic sessions、attempts和Evidence关联 |
| `20260810_0009` | focused_regression_runs及不可变Defect Snapshot |

默认数据库升级：

```powershell
python -m alembic -c backend\alembic.ini upgrade head
```

查看当前版本：

```powershell
python -m alembic -c backend\alembic.ini current
```

## 自定义迁移目标

当前`backend/migrations/env.py`读取`backend/alembic.ini`中的`sqlalchemy.url`，不会自动读取应用环境变量。对非默认数据库迁移时显式覆盖：

```powershell
$env:PYTHONPATH=(Resolve-Path 'backend').Path
@'
from pathlib import Path
from alembic import command
from alembic.config import Config

database = Path('data/custom.db').resolve()
config = Config('backend/alembic.ini')
config.set_main_option('sqlalchemy.url', f'sqlite:///{database.as_posix()}')
command.upgrade(config, 'head')
'@ | python -
```

该差异已列为RC1技术债，不能假设`TEST_WORKBENCH_DATABASE_URL`会改变Alembic CLI目标。

## 备份要求

一致备份必须覆盖：

1. SQLite数据库文件。
2. `TEST_WORKBENCH_EVIDENCE_ROOT`整个目录。
3. `TEST_WORKBENCH_REPORT_ROOT`整个目录（含reports和archives）。
4. 文件清单及SHA256。

恢复后至少执行`PRAGMA quick_check`、`PRAGMA foreign_key_check`、业务表计数、Evidence/Report/Archive hash校验和API下载检查。
