# Test Workbench

Test Workbench 面向 ONU、OLT、光猫等网络设备测试场景。V2 在完整保留 V1 Test Management 闭环的基础上，升级为“ONU 测试能力管理 + 测试执行闭环工作台”：用 Test Skill 沉淀测试目标、参数、步骤、判定标准和证据要求，并以版本化标准库提供 PASS/FAIL/BLOCKED 判断依据。

当前 main 已包含 V2 领域基础、ONU/OLT 本地 Runner 和中文现场检查入口。已具备受控 OLT 动作、ONU Web WAN/Ping 与 PC 连通性证据采集；正式 Skill 执行闭环和真实设备验收仍需完成。系统保持单用户、本地 B/S 定位。

当前阶段与待验收事项见[项目进度](docs/PROJECT_PROGRESS.md)；现场操作见[兼容性检查说明](docs/ONU_LAB_COMPATIBILITY_CHECK.md)。

## 当前能力

- Device Library：设备档案 CRUD。
- Test Case Library：测试用例、步骤、优先级和启停管理。
- Test Execution：项目、设备、环境和用例选择，PASS/FAIL/BLOCKED记录。
- Result Integrity：实际结果、阻塞原因、备注和 LOCKED 不可变保护。
- Evidence：结果或缺陷附件上传、下载、删除及 SHA256 校验。
- Defect & Regression：缺陷状态机、追加式回归和结果联动。
- Environment Snapshot：环境模板、参数和 Run 创建时的不可变快照。
- Report & Archive：不可变HTML报告、单一ZIP归档和完整性校验。
- Test Standards：版本化测试标准、标准要求、产品/客户标准 Profile。
- Test Intelligence：Skill、参数、步骤、执行规则、证据规则及标准绑定。
- Skill Case & Template：Skill 到 Test Case 的实现映射，以及可冻结版本的执行模板。
- Execution Foundation：不可变执行快照、受控 Runner 注册表、执行事件、人工交互和恢复任务模型。

## 技术栈

- 前端：React 19、TypeScript、Vite、Vitest、Testing Library
- 后端：FastAPI、SQLAlchemy、Pydantic Settings、Alembic、Pytest
- 数据库：SQLite
- 部署方式：单机 B/S

## 目录

```text
backend/
  app/core/              配置与日志
  app/db/                Engine、Session、ORM Base和依赖
  app/models/            V1模型及V2 Standard、Skill、Runner、Execution模型
  app/devices/           设备库
  app/test_cases/        测试用例库
  app/test_execution/    项目、Run、Result和Snapshot
  app/defects/           缺陷与回归
  app/evidence/          Evidence元数据与文件存储
  app/environments/      环境模板与快照
  app/reports/           报告、归档、渲染和存储
  migrations/            Alembic迁移
  tests/                 后端测试
frontend/src/
  devices/               设备页面
  testCases/             用例页面
  testExecution/         执行与结果编辑页面
  defects/               缺陷及附件页面
  environments/          环境模板与快照页面
  reports/               报告归档页面
docs/                    架构、数据库、API和验收文档
data/                    SQLite、Evidence、Report、Archive运行数据（Git忽略）
logs/                    运行日志（Git忽略）
```

## 环境要求

- Python 3.12+
- Node.js 24+
- npm 11+

## 初始化

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e "backend[dev]"
Copy-Item .env.example .env
Set-Location frontend
npm.cmd install
Set-Location ..
```

## 数据库迁移

默认迁移目标为 `data/test_workbench.db`。生产启动不会再用 ORM 元数据静默建表；数据库必须先迁移到 Alembic head：

```powershell
.\.venv\Scripts\python -m alembic -c backend\alembic.ini upgrade head
```

当前 Alembic 通过 `backend/alembic.ini`读取迁移URL，不会自动使用`TEST_WORKBENCH_DATABASE_URL`切换目标。对自定义数据库执行迁移时，应通过Alembic Config显式覆盖URL；示例见[数据库文档](docs/DATABASE.md)。

`TEST_WORKBENCH_ALLOW_METADATA_CREATE_ALL` 仅用于测试或明确的本地开发初始化，禁止作为生产迁移替代品。

## 启动

后端：

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload
```

前端：

```powershell
Set-Location frontend
npm.cmd run dev
```

- API：`http://127.0.0.1:8000`
- 健康检查：`GET http://127.0.0.1:8000/api/health`
- 前端：`http://127.0.0.1:5173`

## 配置

后端配置使用`TEST_WORKBENCH_`前缀：

- `TEST_WORKBENCH_APP_ENV`
- `TEST_WORKBENCH_API_PREFIX`
- `TEST_WORKBENCH_DATABASE_URL`
- `TEST_WORKBENCH_LOG_LEVEL`
- `TEST_WORKBENCH_LOG_FILE`
- `TEST_WORKBENCH_EVIDENCE_ROOT`
- `TEST_WORKBENCH_EVIDENCE_MAX_SIZE_MB`
- `TEST_WORKBENCH_REPORT_ROOT`
- `TEST_WORKBENCH_ALLOW_METADATA_CREATE_ALL`（仅测试/开发）

凭据不得写入`.env.example`、文档、Evidence或Git。`.env`、数据库、附件、日志、备份、测试临时目录和构建产物均应保持Git忽略。

## 验证

```powershell
python -m pytest backend/tests -q --basetemp data/pytest
Set-Location frontend
npm.cmd test -- --reporter=dot --maxWorkers=1
npm.cmd run build
```

Windows环境建议固定Vitest单worker，避免Node/Vitest worker内存不足。

## V2 Sprint 0 状态

- V1 Test Management：原有设备、项目、环境、执行、证据、缺陷、回归、报告能力及历史数据均保留。
- V2 数据基础：Alembic `20260918_0020`，覆盖 Standard、Skill、Template、Runner 与 Execution Foundation。
- 兼容原则：历史 Run/Result 不推断不存在的 Skill 或 Standard，使用明确的 `MANUAL` 来源与空 V2 快照。
- 下一阶段：Sprint 1 实现 Skill 管理能力；随后由测试人员共同封装 VLAN 端口绑定、QoS、IPv6 等真实 Skill。
- V1 稳定版记录仍见[发布批准文档](docs/V1_RELEASE_FINAL_APPROVAL.md)。
