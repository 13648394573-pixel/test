# Test Workbench

供网络设备测试工程师本地使用的测试工作台。当前业务范围仅包含 Device Library（设备库），支持设备档案的列表、新建、编辑和删除。

## 技术栈

- 前端：React、TypeScript、Vite
- 后端：FastAPI、SQLAlchemy、Pydantic Settings、Alembic
- 数据库：本地 SQLite
- 测试：Vitest、Testing Library、Pytest

## 目录

```text
backend/
  app/core/        配置与日志
  app/db/          ORM 基类、数据库引擎、会话和依赖
  app/models/      SQLAlchemy 数据模型
  app/devices/     设备 Repository、Service、Schema 和 API
  migrations/      Alembic 数据库迁移
  tests/           后端测试
frontend/
  src/devices/     设备库页面、表单、API client 和测试
docs/              设计与实施计划
data/              本地 SQLite 数据（运行时创建）
logs/              本地日志（运行时创建）
```

## 环境要求

- Python 3.12+
- Node.js 24+
- npm 11+

## 后端开发

在项目根目录初始化环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e "backend[dev]"
Copy-Item .env.example .env
```

应用数据库迁移：

```powershell
.\.venv\Scripts\python -m alembic -c backend\alembic.ini upgrade head
```

启动 API：

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload
```

API 默认地址为 `http://127.0.0.1:8000`，健康检查为 `GET /api/health`。

## Device Library API

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/devices` | 设备列表 |
| `POST` | `/api/devices` | 新建设备 |
| `GET` | `/api/devices/{id}` | 设备详情 |
| `PUT` | `/api/devices/{id}` | 编辑设备 |
| `DELETE` | `/api/devices/{id}` | 删除设备 |

`device_type`、`vendor`、`model`、`serial_number` 必填，序列号不可重复。

## 前端开发

```powershell
Set-Location frontend
npm.cmd install
npm.cmd run dev
```

前端默认地址为 `http://127.0.0.1:5173`，开发服务器会将 `/api` 转发到本地 FastAPI。

## 配置

复制 `.env.example` 为 `.env` 后修改。后端变量使用 `TEST_WORKBENCH_` 前缀：

- `APP_ENV`：运行环境
- `API_PREFIX`：API 前缀
- `DATABASE_URL`：SQLite 连接地址
- `LOG_LEVEL`：日志级别
- `LOG_FILE`：日志文件路径

`.env`、数据库、日志、依赖目录和构建产物不会提交到版本库。

## 验证

```powershell
python -m pytest backend/tests -q
Set-Location frontend
npm.cmd test
npm.cmd run build
```

后端测试覆盖迁移、Repository、Service、CRUD API 和基础设施；前端测试覆盖设备列表、新建、编辑、确认删除和 API client。
