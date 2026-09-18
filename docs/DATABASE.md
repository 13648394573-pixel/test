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

空库迁移至 `20260918_0020` 后共有44张表（含`alembic_version`）。原 V1 表与关系保持不变，V2 以新增表、可空外键和带明确默认值的新字段扩展。

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

### V2 Test Standard 与 Test Intelligence

| 表组 | 表 | 用途 |
|---|---|---|
| Standard | `test_standards`、`standard_requirements` | 版本化标准及可计算的 PASS/FAIL/BLOCKED 要求 |
| Standard Profile | `standard_profiles`、`standard_profile_items`、`project_standard_profiles` | 按产品、客户、地区组合标准，并绑定项目 |
| Skill | `test_skills`、`skill_parameters`、`skill_steps` | 测试能力定义、输入参数和操作步骤 |
| Skill Rules | `skill_execution_rules`、`skill_evidence_rules`、`skill_standard_bindings` | 判定逻辑、证据要求和标准依据 |
| Case Mapping | `skill_cases` | Skill 与 V1 Test Case 的版本化实现映射 |
| Template | `templates`、`template_cases` | 可冻结、可复用的执行模板与用例顺序 |

### V2 Execution Foundation

| 表组 | 表 | 用途 |
|---|---|---|
| Runner Registry | `runner_plugins`、`runner_actions`、`skill_runner_bindings` | 仅登记受控插件和动作标识，不在数据库保存任意脚本正文或命令文本 |
| Execution | `execution_sessions`、`execution_events` | 执行状态机与追加式事件时间线 |
| Human-in-the-loop | `operator_interactions` | 对无法自动化的步骤发出操作提示并记录确认 |
| Recovery | `recovery_tasks` | 中断或失败后的恢复动作与状态 |
| Configuration | `configuration_snapshots` | 执行时使用的非秘密配置快照 |
| Credentials | `credential_references` | 只保存外部凭据引用，不保存用户名密码或令牌原文 |

`test_runs`、`run_results` 新增的 V2 来源、快照和执行关联字段均允许 V1 历史记录使用兼容默认值。迁移不会根据旧用例名称猜测 Skill 或 Standard。

## 不变性规则

- `device_snapshot`、`case_snapshot`、`profile_snapshot`创建后不可修改。
- `snapshot_version`固定为1。
- RunResult从DRAFT单向进入LOCKED，不能解锁；LOCKED结果字段不可修改。
- Defect只能来源于LOCKED FAIL/BLOCKED Result，且一个Result最多一个Defect。
- Regression记录不可更新或删除。
- Evidence元数据不可更新，文件内容通过SHA256验证。
- Report和Archive记录不可更新或删除；文件hash不匹配时拒绝下载或归档。
- Focused Regression关联及Defect Snapshot不可更新或删除；每次回归必须产生新的TestRun。
- PUBLISHED/RETIRED 的 Standard、Profile、Skill、Template 和 Runner 定义采用版本化演进，不原地篡改历史语义。
- Execution Event 追加写入；活动执行会话具有唯一性约束，终态记录可长期保留。
- 数据库模型不包含脚本正文、任意命令文本、Web选择器或秘密凭据字段。

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
| `20260811_0010` | Run可读编号、历史索引、Evidence与Result多对多关联基础 |
| `20260918_0011` | V1基线守卫；确认升级起点和完整性 |
| `20260918_0012` | 版本化测试标准、要求和标准Profile |
| `20260918_0013` | Skill、参数和步骤 |
| `20260918_0014` | Skill执行规则、证据规则和标准绑定 |
| `20260918_0015` | Skill Case映射与Template |
| `20260918_0016` | V2 Run/Result不可变快照与兼容来源字段 |
| `20260918_0017` | 恢复项目规划元数据 |
| `20260918_0018` | 受控Runner Plugin/Action注册表 |
| `20260918_0019` | Execution Session/Event、人工交互与恢复任务 |
| `20260918_0020` | 凭据引用、配置快照及执行状态关联 |

默认数据库升级：

```powershell
python -m alembic -c backend\alembic.ini upgrade head
```

生产应用启动前必须完成迁移并处于 Alembic head。应用不会对空库或旧库静默执行 `Base.metadata.create_all()`；`TEST_WORKBENCH_ALLOW_METADATA_CREATE_ALL=true` 只允许测试或明确的本地开发初始化使用。

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

不能假设`TEST_WORKBENCH_DATABASE_URL`会改变Alembic CLI目标；安装器/双击启动器中的自动迁移编排属于后续 Sprint，不在 Sprint 0 范围内。

## 备份要求

一致备份必须覆盖：

1. SQLite数据库文件。
2. `TEST_WORKBENCH_EVIDENCE_ROOT`整个目录。
3. `TEST_WORKBENCH_REPORT_ROOT`整个目录（含reports和archives）。
4. 文件清单及SHA256。

恢复后至少执行`PRAGMA quick_check`、`PRAGMA foreign_key_check`、业务表计数、Evidence/Report/Archive hash校验和API下载检查。

V1→V2 升级还应核对 Run、Result、Evidence、Defect、Regression、Report、Archive 的数量与关键 SHA256，并确认历史记录保持 `source/result_source='MANUAL'`、V2 快照为空且没有被自动绑定到任何 Skill 或 Standard。

## Migration 20260811_0010

- `test_runs.run_no`：非空唯一可读编号，格式 `RUN-000001`；历史数据按 `started_at, id` 回填。
- `evidence_run_result_links`：Evidence 与 RunResult 的多对多关联表，复合主键为 `(evidence_id, run_result_id)`。
- 索引：Run 编号唯一索引、Run 开始时间索引、项目/状态/开始时间复合索引、Evidence Link 的 Result 索引。

`evidences.run_result_id` 保留为主归属以兼容旧数据和存储路径。迁移为既有 Result Evidence 自动创建主 Link；Defect Evidence 不受影响。
