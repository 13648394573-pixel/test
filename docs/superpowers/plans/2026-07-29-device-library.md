# Device Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现仅面向个人测试工程师的设备档案 CRUD，并提供可迁移的 SQLite 表、分层后端和 React 页面。

**Architecture:** 后端按 model → repository → service → API 分层，FastAPI 通过请求级 SQLAlchemy Session 访问 SQLite。前端以单个 Device Library 页面、API client 和可复用表单组成，不引入路由器或状态框架。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2、Alembic、Pydantic、Pytest、React 19、TypeScript、Vitest、Testing Library。

## Global Constraints

- 仅实现 Device Library。
- 不创建测试项目、环境、测试用例或自动化功能。
- 字段限定为 device_type、vendor、model、serial_number、mac_address、hardware_version、software_version、created_at、updated_at；另使用 UUID `id` 作为必要主键。
- device_type、vendor、model、serial_number 必填；其余业务字段可空。
- serial_number 唯一；删除使用直接删除，不增加软删除字段。

---

### Task 1: Device model and migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Create: `backend/migrations/versions/20260729_0001_create_devices.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/device.py`
- Create: `backend/tests/test_device_migration.py`
- Modify: `backend/pyproject.toml`

**Interfaces:**
- Produces: SQLAlchemy `Device` mapped to `devices`; Alembic revision `20260729_0001`.

- [ ] Write a migration test that upgrades a temporary SQLite database and asserts the exact columns, primary key and serial-number unique constraint.
- [ ] Run the migration test and verify it fails because Alembic/migration files are absent.
- [ ] Add Alembic configuration, model and one migration.
- [ ] Run the migration test and all backend tests.

### Task 2: Repository, service and CRUD API

**Files:**
- Create: `backend/app/devices/__init__.py`
- Create: `backend/app/devices/schemas.py`
- Create: `backend/app/devices/repository.py`
- Create: `backend/app/devices/service.py`
- Create: `backend/app/devices/router.py`
- Create: `backend/app/db/dependencies.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_device_repository.py`
- Create: `backend/tests/test_device_service.py`
- Create: `backend/tests/test_device_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: `DeviceRepository`, `DeviceService`, `GET/POST/PUT/DELETE /api/devices`.

- [ ] Write repository tests for create/list/get/update/delete using a real temporary SQLite database.
- [ ] Verify repository tests fail because the repository is absent.
- [ ] Implement the minimal repository and rerun tests.
- [ ] Write service tests for duplicate serial numbers and missing devices.
- [ ] Verify service tests fail, then implement service exceptions and orchestration.
- [ ] Write API tests for list, create, get, update, delete, validation, 404 and 409 responses.
- [ ] Verify API tests fail, then implement schemas, session dependency, router and app registration.
- [ ] Run all backend tests.

### Task 3: Device Library frontend

**Files:**
- Create: `frontend/src/devices/types.ts`
- Create: `frontend/src/devices/api.ts`
- Create: `frontend/src/devices/DeviceForm.tsx`
- Create: `frontend/src/devices/DeviceLibraryPage.tsx`
- Create: `frontend/src/devices/DeviceLibraryPage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/index.css`
- Modify: `frontend/vite.config.ts`

**Interfaces:**
- Produces: `DeviceApi`, `DeviceLibraryPage`, create/edit/delete UI backed by `/api/devices`.

- [ ] Write UI tests with an in-memory `DeviceApi` for list, create, edit and confirmed delete.
- [ ] Run the focused test and verify failure because Device Library components are absent.
- [ ] Implement types, API client, form and page with only the required fields.
- [ ] Replace the Sprint 0 shell with Device Library and add `/api` dev proxy.
- [ ] Run focused and complete frontend tests, then run production build.

### Task 4: Documentation and final verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Documents: `alembic upgrade head`, Device Library API and development validation.

- [ ] Document migration and Device Library commands without describing future modules.
- [ ] Run `python -m pytest backend/tests -q`.
- [ ] Run `npm.cmd test -- --reporter=dot`.
- [ ] Run `npm.cmd run build`.
- [ ] Run `git status --short` and confirm changes are confined to this plan.
