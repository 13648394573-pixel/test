# Defect & Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a personal defect lifecycle and append-only regression history linked to immutable test execution evidence.

**Architecture:** Add a self-contained `defects` module following Router → Schema → Service → Repository → Model. The module references `RunResult` read-only through foreign keys and repository queries; it never writes Device, TestCase, TestRun, RunResult, or snapshots.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, SQLite, Pydantic 2, React, TypeScript, Vitest, Testing Library.

## Global Constraints

- `defects.source_run_result_id` is UNIQUE: one failed evidence item creates at most one Defect.
- Defects may originate only from `FAIL` or `BLOCKED` RunResult records.
- Regression records are append-only and belong to a Defect.
- Regression `PASS` changes `RESOLVED → CLOSED`; `FAIL` changes `RESOLVED → REOPENED`; `BLOCKED` records history without changing Defect status.
- Illegal state transitions return HTTP 409.
- Do not modify files under `app/devices`, `app/test_cases`, `app/test_execution`, `frontend/src/devices`, `frontend/src/testCases`, or `frontend/src/testExecution`.
- Do not add attachments, logs, comments, Jira/Git integrations, AI analysis, or automated regression.
- Do not commit during implementation; version freeze happens only after review.

---

### Task 1: Migration and ORM models

**Files:**
- Create: `backend/tests/test_defect_migration.py`
- Create: `backend/app/models/defect.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/migrations/versions/20260730_0004_create_defects.py`

**Interfaces:**
- Produces: `Defect` and `Regression` SQLAlchemy models.
- `Defect.source_run_result_id` references `run_results.id` with UNIQUE and RESTRICT semantics.
- `Regression(defect_id, verification_run_result_id)` is unique.

- [ ] Write a migration test that upgrades a temporary database to head and asserts both tables, columns, foreign keys, unique constraints, and status/result checks.
- [ ] Run `python -m pytest backend/tests/test_defect_migration.py -q`; verify RED because the tables do not exist.
- [ ] Add models with UUID string primary keys, timestamps, relationships, and database checks:
  - Defect severity: `S1/S2/S3/S4`.
  - Defect status: `OPEN/IN_PROGRESS/RESOLVED/REOPENED/CLOSED`.
  - Regression result: `PASS/FAIL/BLOCKED`.
- [ ] Add Alembic revision `20260730_0004`, down revision `20260729_0003`.
- [ ] Export the models from `app.models`.
- [ ] Run migration tests and existing migration tests; verify GREEN.

### Task 2: Repository persistence and read-only evidence

**Files:**
- Create: `backend/app/defects/__init__.py`
- Create: `backend/app/defects/repository.py`
- Create: `backend/tests/test_defect_repository.py`

**Interfaces:**
- Produces `DefectRepository`.
- Methods:
  - `list_defects(status: str | None, severity: str | None) -> list[Defect]`
  - `get_defect(defect_id: str) -> Defect | None`
  - `get_run_result(result_id: str) -> RunResult | None`
  - `source_has_defect(result_id: str) -> bool`
  - `next_defect_code() -> str`
  - `create_defect(values: Mapping[str, Any]) -> Defect`
  - `update_defect(defect: Defect, values: Mapping[str, Any]) -> Defect`
  - `create_regression(defect: Defect, values: Mapping[str, Any], defect_updates: Mapping[str, Any]) -> Regression`

- [ ] Write repository tests for ordered listing/filtering, eager-loaded evidence, unique source enforcement, updates, append-only regression creation, and atomic Defect status update.
- [ ] Run repository tests; verify RED because `app.defects.repository` is absent.
- [ ] Implement only the persistence needed by the tests. Use `selectinload` for source/verification RunResult and regression history.
- [ ] Ensure `create_regression` commits the Regression and Defect state change in one transaction and rolls back both on error.
- [ ] Run migration and repository tests; verify GREEN.

### Task 3: Service lifecycle and validation

**Files:**
- Create: `backend/app/defects/service.py`
- Create: `backend/tests/test_defect_service.py`

**Interfaces:**
- Produces `DefectService`.
- Errors:
  - `DefectNotFoundError`
  - `RunResultEvidenceNotFoundError`
  - `InvalidDefectSourceError`
  - `DuplicateDefectSourceError`
  - `InvalidDefectTransitionError`
  - `ClosedDefectError`
  - `InvalidRegressionEvidenceError`
  - `DuplicateRegressionError`
- Public methods: list, get, create, update, transition, list regressions, create regression.

- [ ] Write tests proving Defect creation accepts only FAIL/BLOCKED evidence, rejects duplicate source evidence, and leaves RunResult/snapshots unchanged.
- [ ] Write parameterized state tests:
  - `OPEN → IN_PROGRESS`
  - `IN_PROGRESS → RESOLVED` only with non-empty resolution notes
  - `REOPENED → IN_PROGRESS`
  - all other manual transitions rejected.
- [ ] Write regression tests proving only RESOLVED defects accept new records, evidence must be executed and use the same `case_source_id`, duplicates are rejected, and records cannot be updated through the service.
- [ ] Write outcome tests for PASS/CLOSED, FAIL/REOPENED, and BLOCKED/no state change.
- [ ] Run service tests; verify RED because service is absent.
- [ ] Implement the minimal state machine and evidence validation.
- [ ] Run repository and service tests; verify GREEN.

### Task 4: Schemas, Router, and HTTP error mapping

**Files:**
- Create: `backend/app/defects/schemas.py`
- Create: `backend/app/defects/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_defect_api.py`

**Interfaces:**
- Routes:
  - `GET /api/defects`
  - `POST /api/defects`
  - `GET /api/defects/{defect_id}`
  - `PUT /api/defects/{defect_id}`
  - `PUT /api/defects/{defect_id}/status`
  - `GET /api/defects/{defect_id}/regressions`
  - `POST /api/defects/{defect_id}/regressions`
- HTTP mapping: missing resources 404, duplicate/transition/state/evidence conflicts 409, malformed payload 422.

- [ ] Write API lifecycle tests using existing Device/TestCase/TestExecution endpoints to create real RunResult evidence.
- [ ] Assert no DELETE endpoint, duplicate Defect source returns 409, illegal state returns 409, and regression outcomes update Defect as specified.
- [ ] Capture original RunResult JSON before Defect operations and assert it is unchanged afterward.
- [ ] Run API tests; verify RED with route 404.
- [ ] Add strict Pydantic input schemas, read schemas with nested immutable evidence, router dependencies, and application exception handlers.
- [ ] Register only the new router in `main.py`.
- [ ] Run all backend tests; verify GREEN.

### Task 5: Frontend API and Defect page

**Files:**
- Create: `frontend/src/defects/types.ts`
- Create: `frontend/src/defects/api.ts`
- Create: `frontend/src/defects/api.test.ts`
- Create: `frontend/src/defects/DefectPage.tsx`
- Create: `frontend/src/defects/DefectPage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- `DefectApi`: list, create, get, update, transition, listRegressions, createRegression.
- `DefectPage` consumes `DefectApi` and existing `TestExecutionApi` read methods.

- [ ] Write API client tests for every route and backend error detail propagation; verify RED before adding `api.ts`.
- [ ] Implement API client and types; verify API tests GREEN.
- [ ] Write page tests for:
  - listing/filtering Defects;
  - selecting eligible FAIL/BLOCKED source evidence and creating one Defect;
  - editing Defect details;
  - valid lifecycle buttons;
  - selecting same-case verification evidence;
  - PASS, FAIL, and BLOCKED regression behavior and history display.
- [ ] Run page tests; verify RED before adding the page.
- [ ] Implement a single “Defect & Regression” page. Load execution history through existing `TestExecutionApi`; never modify that API or page.
- [ ] Add application navigation and scoped CSS, preserving existing module props.
- [ ] Run targeted frontend tests; verify GREEN.

### Task 6: Full verification and scope audit

**Files:** No production changes unless a new failing test demonstrates a Sprint 4 defect.

- [ ] Run `python -m pytest backend/tests -q`.
- [ ] Run `npm.cmd test -- --reporter=dot --maxWorkers=1`.
- [ ] Run `npm.cmd run build`.
- [ ] Run Alembic head verification and confirm `20260730_0004` is head.
- [ ] Inspect `git diff --check`, `git status --short`, and changed paths.
- [ ] Confirm no changed paths inside existing Device/TestCase/TestExecution module directories.
- [ ] Confirm no database, `node_modules`, `dist`, cache, log, or temporary file is tracked.
- [ ] Stop with the feature branch and worktree intact for code review.
