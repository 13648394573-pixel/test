# Test Workbench

网络设备测试工作台。本仓库当前仅包含 Sprint 0 基础工程，不包含设备、项目、用例、执行、缺陷或报告等业务模块。

## 技术栈

- 前端：React、TypeScript、Vite
- 后端：FastAPI、SQLAlchemy、Pydantic Settings
- 数据库：本地 SQLite
- 测试：Vitest、Testing Library、Pytest

## 目录

```text
backend/
  app/core/        配置与日志
  app/db/          ORM 基类、数据库引擎和会话
  tests/           后端测试
frontend/
  src/             React 应用壳与测试
docs/              设计与实施计划
data/              本地 SQLite 数据（运行时创建）
logs/              本地日志（运行时创建）
```

## 环境要求

- Python 3.12+
- Node.js 24+
- npm 11+

## 后端开发

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e "backend[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload
```

API 默认地址为 `http://127.0.0.1:8000`，健康检查为 `GET /api/health`。首次启动自动创建 `data/test_workbench.db` 和日志目录。

## 前端开发

```powershell
Set-Location frontend
npm.cmd install
npm.cmd run dev
```

前端默认地址为 `http://127.0.0.1:5173`。

## 配置

复制 `.env.example` 为 `.env` 后修改。所有后端变量均使用 `TEST_WORKBENCH_` 前缀：

- `APP_ENV`：运行环境
- `API_PREFIX`：API 前缀
- `DATABASE_URL`：SQLite 连接地址
- `LOG_LEVEL`：日志级别
- `LOG_FILE`：日志文件路径

`.env`、数据库和日志均不会提交到版本库。

## 验证

```powershell
python -m pytest backend/tests -q
Set-Location frontend
npm.cmd test
npm.cmd run build
```

后端测试验证配置覆盖、SQLite 连接与会话、日志落盘和健康检查；前端测试验证基础应用壳，构建命令验证 TypeScript 与生产产物。
