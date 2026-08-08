# Test Workbench

Test Workbench 面向 ONU、OLT、光猫等网络设备测试场景，长期目标是建设供测试工程师本地使用的个人自动化测试平台。当前 `v1.0.0` 已完成 Sprint 0–7，交付设备、用例、环境、手工执行记录、Evidence、缺陷回归及报告归档闭环，为后续自动化执行提供稳定的数据与流程基础。

`v1.0.0` 尚未包含脚本自动执行；自动化能力将在后续版本中根据真实测试流程逐步规划和实现。当前版本仍保持单用户、本地B/S架构，不包含 AI、多用户权限、企业协作或云部署。

## 当前能力

- Device Library：设备档案 CRUD。
- Test Case Library：测试用例、步骤、优先级和启停管理。
- Test Execution：项目、设备、环境和用例选择，PASS/FAIL/BLOCKED记录。
- Result Integrity：实际结果、阻塞原因、备注和 LOCKED 不可变保护。
- Evidence：结果或缺陷附件上传、下载、删除及 SHA256 校验。
- Defect & Regression：缺陷状态机、追加式回归和结果联动。
- Environment Snapshot：环境模板、参数和 Run 创建时的不可变快照。
- Report & Archive：不可变HTML报告、单一ZIP归档和完整性校验。

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
  app/models/            全部SQLAlchemy模型
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

默认迁移目标为 `data/test_workbench.db`：

```powershell
.\.venv\Scripts\python -m alembic -c backend\alembic.ini upgrade head
```

当前 Alembic 通过 `backend/alembic.ini`读取迁移URL，不会自动使用`TEST_WORKBENCH_DATABASE_URL`切换目标。对自定义数据库执行迁移时，应通过Alembic Config显式覆盖URL；示例见[数据库文档](docs/DATABASE.md)。

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

凭据不得写入`.env.example`、文档、Evidence或Git。`.env`、数据库、附件、日志、备份、测试临时目录和构建产物均应保持Git忽略。

## 验证

```powershell
python -m pytest backend/tests -q --basetemp data/pytest
Set-Location frontend
npm.cmd test -- --reporter=dot --maxWorkers=1
npm.cmd run build
```

Windows环境建议固定Vitest单worker，避免Node/Vitest worker内存不足。

## 发布状态

- 功能基线：Sprint 0–7已完成。
- 最新自动验证：后端117项、前端39项、生产构建通过。
- Beta：真实ONU online、O5、IPoE、PPPoE和网络连通闭环通过。
- Stable：`v1.0.0`已于2026-08-08正式发布，最终验证与批准记录见[发布批准文档](docs/V1_RELEASE_FINAL_APPROVAL.md)。
- 后续方向：基于维护期真实使用数据规划自动化测试能力，不在`v1.0.0`维护阶段直接扩展核心范围。
