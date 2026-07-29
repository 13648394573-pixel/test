# Test Workbench Sprint 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可启动、可测试的 React + FastAPI + SQLite 基础工程，不包含任何业务模块。

**Architecture:** 前后端分目录；React/Vite 提供单页壳，FastAPI 提供本地 API。后端以配置、日志、数据库三个基础模块组成，SQLite 数据文件与附件/日志目录均由配置控制。

**Tech Stack:** React 19、TypeScript 5、Vite 7、FastAPI、SQLAlchemy 2、Pydantic Settings、SQLite、Pytest、Vitest。

## Global Constraints

- 不实现设备、项目、用例、执行、缺陷、报告等业务模块。
- 优先简单实现，所有可观察行为必须有测试。
- 本地运行，不依赖云服务。

---

### Task 1: Backend foundation

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/logging.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/tests/test_config.py`
- Create: `backend/tests/test_database.py`
- Create: `backend/tests/test_logging.py`
- Create: `backend/tests/test_health.py`

**Interfaces:**
- Produces: `Settings`, `create_database_engine()`, `create_session_factory()`, `configure_logging()`, FastAPI `app`.

- [ ] Write config, database, logging and health tests before production modules exist.
- [ ] Run `python -m pytest backend/tests -q` and confirm collection/import failure.
- [ ] Implement the minimum backend foundation.
- [ ] Re-run backend tests and confirm all pass.

### Task 2: Frontend foundation

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.app.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/App.test.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/test/setup.ts`

**Interfaces:**
- Produces: Vite dev/build entry and a tested application shell.

- [ ] Write the app-shell test before `App.tsx` exists.
- [ ] Run the frontend test and confirm the missing-module failure.
- [ ] Implement the minimum React shell and styles.
- [ ] Run tests and production build.

### Task 3: Configuration and developer documentation

**Files:**
- Create: `.env.example`
- Create: `.gitignore`
- Create: `README.md`

**Interfaces:**
- Documents: installation, configuration, development commands, tests, directory responsibilities and non-business Sprint 0 scope.

- [ ] Add safe local defaults and ignore runtime/build artifacts.
- [ ] Document Windows development startup and validation commands.
- [ ] Run the complete backend tests, frontend tests and frontend build.
- [ ] Compare the result against all eight Sprint 0 requirements.
