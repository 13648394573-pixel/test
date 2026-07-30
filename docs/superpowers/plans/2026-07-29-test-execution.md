# Test Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add manual test projects and traceable test runs whose device and test-case data remain historically stable.

**Architecture:** Preserve Router → Schema → Service → Repository → Model. A project stores logical test-case selections; creating a run loads the current Device/TestCase records once, writes immutable version-1 snapshots, and creates all RunResult rows in the same transaction.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Alembic, SQLite, Pytest, React, TypeScript, Vitest, Testing Library.

## Global Constraints

- Do not modify files inside `backend/app/devices`, `backend/app/test_cases`, `frontend/src/devices`, or `frontend/src/testCases`.
- TestProject has no device field.
- ProjectCaseSelection stores only `project_id` and `case_source_id`.
- RunResult accepts only NULL, PASS, FAIL, or BLOCKED.
- Do not implement attachments, logging features, defects, regression, automation, AI, or reports.
- Do not commit or merge during implementation.

---

### Task 1: Migration and execution models

**Files:**
- Create: `backend/tests/test_test_execution_migration.py`
- Create: `backend/app/models/test_execution.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/migrations/versions/20260729_0003_create_test_execution.py`

**Interfaces:**
- Produces tables `test_projects`, `project_case_selections`, `test_runs`, and `run_results`.
- Produces ORM classes `TestProject`, `ProjectCaseSelection`, `TestRun`, and `RunResult`.

- [ ] Write a migration test that upgrades to head and asserts all columns, keys, logical source IDs, snapshot JSON fields, version defaults, result check constraint, and cascades within the new module.
- [ ] Run the migration test and verify it fails because the four tables are absent.
- [ ] Implement the four ORM models with UUID IDs, timestamps, ordered relationships, composite selection key, and result uniqueness.
- [ ] Add immutable assignment guards for `device_snapshot`, `case_snapshot`, and both snapshot-version fields.
- [ ] Add Alembic revision `20260729_0003`, based on `20260729_0002`.
- [ ] Run migration and existing database tests; verify they pass.

### Task 2: Snapshot builders and repository transactions

**Files:**
- Create: `backend/tests/test_test_execution_repository.py`
- Create: `backend/app/test_execution/__init__.py`
- Create: `backend/app/test_execution/snapshots.py`
- Create: `backend/app/test_execution/repository.py`

**Interfaces:**
- Produces `build_device_snapshot(device)` and `build_case_snapshot(test_case)`.
- Produces project CRUD, run creation/history/detail, result update, and `project_has_runs`.

- [ ] Write failing tests proving snapshots contain literal device fields and ordered case steps, and remain unchanged after source records change.
- [ ] Write failing tests for project aggregate CRUD, atomic run/result creation, history ordering, result update, and cascade behavior inside the module.
- [ ] Run repository tests and verify failure because the module is absent.
- [ ] Implement version-1 snapshot builders and one-transaction repository mutations with rollback.
- [ ] Run repository and migration tests; verify they pass without warnings.

### Task 3: Service rules

**Files:**
- Create: `backend/tests/test_test_execution_service.py`
- Create: `backend/app/test_execution/service.py`

**Interfaces:**
- Produces `TestExecutionService` plus project/run/result not-found errors, invalid-source errors, and project-history conflict error.
- Consumes existing DeviceRepository and TestCaseRepository without changing them.

- [ ] Write failing tests for missing/disabled selections, missing device, snapshot creation at run time, immutable history after source edits, BLOCKED results, automatic completion, and delete rejection when history exists.
- [ ] Run service tests and verify failure because the service is absent.
- [ ] Implement project validation, run snapshot generation, result transitions, and completion timestamps.
- [ ] Run service and repository tests; verify they pass.

### Task 4: Schemas and API

**Files:**
- Create: `backend/tests/test_test_execution_api.py`
- Create: `backend/app/test_execution/schemas.py`
- Create: `backend/app/test_execution/router.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces Project CRUD, run creation/detail/history, and result-update endpoints.
- Maps missing resources to 404, history deletion conflict to 409, and invalid payload/source selections to 422.

- [ ] Write failing API lifecycle tests using real Device and TestCase API setup.
- [ ] Assert Project CRUD, run creation snapshots, run history, PASS/FAIL/BLOCKED updates, automatic completion, 404, 409, and 422.
- [ ] Run API tests and verify 404 because routes are absent.
- [ ] Implement trimmed Pydantic schemas, router dependencies, exception handlers, and router registration.
- [ ] Run all backend tests and verify they pass.

### Task 5: Frontend API client

**Files:**
- Create: `frontend/src/testExecution/types.ts`
- Create: `frontend/src/testExecution/api.ts`
- Create: `frontend/src/testExecution/api.test.ts`

**Interfaces:**
- Produces typed Project, Run, RunResult, snapshot, and TestExecutionApi contracts.

- [ ] Write failing tests for Project CRUD, run creation/detail/history, result update, and API detail errors.
- [ ] Run the client tests and verify failure because the module is absent.
- [ ] Implement `/api/test-projects` and `/api/test-runs` requests.
- [ ] Run client tests and verify they pass.

### Task 6: Manual execution page

**Files:**
- Create: `frontend/src/testExecution/TestExecutionPage.tsx`
- Create: `frontend/src/testExecution/TestExecutionPage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes TestExecutionApi, DeviceApi, and TestCaseApi.
- Produces project management, device selection, run creation, snapshot step display, result controls, and run history.

- [ ] Write failing page tests for project creation/edit/delete, case selection, device selection, run creation, snapshot rendering, PASS/FAIL/BLOCKED saving, and history display.
- [ ] Write a failing App test for switching to Test Execution and back to existing modules.
- [ ] Run UI tests and verify failure because the page/navigation are absent.
- [ ] Implement the page using current list APIs and accessible controls.
- [ ] Add the third module entry and focused styles without changing existing module files.
- [ ] Run all frontend tests with `--maxWorkers=1`; verify they pass.

### Task 7: Full regression and scope audit

**Files:**
- No production files created in this task.

**Interfaces:**
- Verifies Sprint 3 and existing Device/TestCase behavior.

- [ ] Upgrade a temporary SQLite database to Alembic head and print the revision/table list.
- [ ] Run `python -m pytest backend/tests -q`.
- [ ] Run `npm.cmd test -- --reporter=dot --maxWorkers=1`.
- [ ] Run `npm.cmd run build`.
- [ ] Run `git diff --check`, confirm forbidden module directories are untouched, and report `git status`.
