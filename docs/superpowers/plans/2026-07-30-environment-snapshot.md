# Environment Snapshot Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add reusable environment profiles and immutable environment snapshots to TestRun while preserving historical compatibility.

**Architecture:** Add an `environments` domain following Router → Schema → Service → Repository → Model. Test execution resolves an enabled profile during run creation, captures a versioned JSON snapshot including `captured_at`, and persists the run, results, and snapshot in one repository transaction.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, SQLite, React, TypeScript, Vitest.

---

### Task 1: Migration and model contracts

**Files:**
- Create: `backend/tests/test_environment_migration.py`
- Create: `backend/tests/test_environment_models.py`
- Create: `backend/migrations/versions/20260730_0006_environment_snapshot.py`
- Create: `backend/app/models/environment.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/test_execution.py`

- [ ] Write migration/model tests for profile, parameter, snapshot constraints and immutable snapshot updates.
- [ ] Run the focused tests and confirm they fail for missing Sprint 6 structures.
- [ ] Implement the ORM models and migration.
- [ ] Run focused tests to green.

### Task 2: Environment profile domain

**Files:**
- Create: `backend/tests/test_environment_repository.py`
- Create: `backend/tests/test_environment_service.py`
- Create: `backend/app/environments/__init__.py`
- Create: `backend/app/environments/repository.py`
- Create: `backend/app/environments/service.py`
- Create: `backend/app/environments/schemas.py`
- Create: `backend/app/environments/snapshots.py`

- [ ] Write repository/service tests for CRUD, parameter replacement, duplicate validation, enabled selection, and profile deletion with history.
- [ ] Confirm the focused tests fail.
- [ ] Implement transactional repository and service behavior.
- [ ] Run focused tests to green.

### Task 3: Run creation and API

**Files:**
- Create: `backend/tests/test_environment_api.py`
- Modify: `backend/tests/test_test_execution_api.py`
- Modify: `backend/tests/test_test_execution_repository.py`
- Modify: `backend/tests/test_test_execution_service.py`
- Create: `backend/app/environments/router.py`
- Modify: `backend/app/test_execution/repository.py`
- Modify: `backend/app/test_execution/service.py`
- Modify: `backend/app/test_execution/schemas.py`
- Modify: `backend/app/test_execution/router.py`
- Modify: `backend/app/main.py`

- [ ] Write API and run-creation tests for enabled-profile enforcement, captured snapshot, immutability, and old-run compatibility.
- [ ] Confirm the focused tests fail.
- [ ] Implement profile API and TestRun snapshot integration.
- [ ] Run all backend tests to green.

### Task 4: Frontend profile and snapshot flow

**Files:**
- Create: `frontend/src/environments/types.ts`
- Create: `frontend/src/environments/api.ts`
- Create: `frontend/src/environments/api.test.ts`
- Create: `frontend/src/environments/EnvironmentProfilePage.tsx`
- Create: `frontend/src/environments/EnvironmentProfilePage.test.tsx`
- Create: `frontend/src/environments/EnvironmentSnapshotPanel.tsx`
- Create: `frontend/src/environments/EnvironmentSnapshotPanel.test.tsx`
- Modify: `frontend/src/testExecution/types.ts`
- Modify: `frontend/src/testExecution/api.ts`
- Modify: `frontend/src/testExecution/api.test.ts`
- Modify: `frontend/src/testExecution/TestExecutionPage.tsx`
- Modify: `frontend/src/testExecution/TestExecutionPage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`

- [ ] Write tests for profile CRUD, mandatory enabled-profile selection, snapshot display, and no-snapshot compatibility.
- [ ] Confirm focused tests fail.
- [ ] Implement the pages and API integration.
- [ ] Run frontend tests to green.

### Task 5: Full verification

- [ ] Run `python -m pytest backend/tests -q`.
- [ ] Run `npm.cmd test -- --reporter=dot --maxWorkers=1`.
- [ ] Run `npm.cmd run build`.
- [ ] Inspect diff for Sprint 6-only changes and excluded artifacts.
- [ ] Report Git status without committing; version solidification remains a separate review step.
