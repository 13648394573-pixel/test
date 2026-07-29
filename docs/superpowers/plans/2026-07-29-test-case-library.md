# Test Case Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manually maintained Test Case Library with ordered steps, aggregate CRUD, and a React management page.

**Architecture:** Keep the existing Router → Schema → Service → Repository → Model layering. `TestCase` is the aggregate root; repository operations persist the case and its ordered `CaseStep` children in one transaction, while the service validates uniqueness and assigns continuous step numbers.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Alembic, SQLite, Pytest, React, TypeScript, Vitest, Testing Library.

## Global Constraints

- Do not modify Device Library business files.
- Do not implement test execution, screenshots, defects, automation, or standalone CaseStep APIs.
- Delete TestCase and CaseStep records physically; deleting a TestCase cascades to its steps.
- Replace the complete step collection on update.
- Do not commit changes during implementation; leave the feature branch ready for review.

---

### Task 1: Migration and ORM aggregate

**Files:**
- Create: `backend/tests/test_test_case_migration.py`
- Create: `backend/app/models/test_case.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/migrations/versions/20260729_0002_create_test_case_library.py`

**Interfaces:**
- Produces: `TestCase.steps: list[CaseStep]`, `CaseStep.test_case_id`, and database tables `test_cases` / `case_steps`.

- [ ] Write a migration test that upgrades to head and asserts both tables, columns, primary keys, unique `case_code`, foreign key cascade, and unique `(test_case_id, step_number)`.
- [ ] Run the migration test and verify it fails because the tables are absent.
- [ ] Add SQLAlchemy models with UUID string IDs, timestamps, ordered relationship, `delete-orphan`, database constraints, and foreign-key cascade.
- [ ] Add Alembic revision `20260729_0002`, based on `20260729_0001`, creating parent then child and dropping child then parent.
- [ ] Run the migration test and existing database tests; verify they pass.

### Task 2: Repository aggregate persistence

**Files:**
- Create: `backend/tests/test_test_case_repository.py`
- Create: `backend/app/test_cases/__init__.py`
- Create: `backend/app/test_cases/repository.py`

**Interfaces:**
- Produces: `TestCaseRepository.list/get/get_by_case_code/create/update/delete`.
- Consumes: model values plus step dictionaries containing `step_number`, `action`, and `expected_result`.

- [ ] Write failing tests for aggregate create/list/get, full step replacement, same-transaction rollback, and cascade delete.
- [ ] Run the repository tests and verify failure because the repository does not exist.
- [ ] Implement aggregate persistence with one commit per public mutation and rollback on SQLAlchemy failure.
- [ ] Run repository and migration tests; verify they pass.

### Task 3: Service rules

**Files:**
- Create: `backend/tests/test_test_case_service.py`
- Create: `backend/app/test_cases/service.py`

**Interfaces:**
- Produces: `TestCaseService.list/get/create/update/delete`, `TestCaseNotFoundError`, and `DuplicateCaseCodeError`.
- Consumes: write values with an unnumbered `steps` list.

- [ ] Write failing tests for duplicate case code, missing aggregate, continuous numbering after reorder, and update replacement.
- [ ] Run the service tests and verify failure because the service does not exist.
- [ ] Implement uniqueness checks, missing-case errors, and step numbering `1..N` before repository calls.
- [ ] Run service and repository tests; verify they pass.

### Task 4: Schemas and API

**Files:**
- Create: `backend/tests/test_test_case_api.py`
- Create: `backend/app/test_cases/schemas.py`
- Create: `backend/app/test_cases/router.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: CRUD endpoints under `/api/test-cases`; nested steps have no IDs in writes and include IDs/timestamps/step numbers in reads.

- [ ] Write failing API tests for CRUD, nested step ordering/replacement, cascade delete evidence, 404, 409, and 422 validation.
- [ ] Run the API tests and verify 404 or import failure because routes are absent.
- [ ] Add Pydantic schemas for P0/P1/P2/P3, trimmed required strings, at least one step, and ORM read serialization.
- [ ] Add the router and map service errors to 404/409 in the application without altering Device routes.
- [ ] Run all backend tests and verify they pass.

### Task 5: Frontend API and types

**Files:**
- Create: `frontend/src/testCases/types.ts`
- Create: `frontend/src/testCases/api.ts`
- Create: `frontend/src/testCases/api.test.ts`

**Interfaces:**
- Produces: `TestCase`, `TestCaseInput`, `TestCaseApi`, and `testCaseApi`.

- [ ] Write failing client tests for list/create/update/delete request contracts and API detail errors.
- [ ] Run the client test and verify failure because the module is absent.
- [ ] Implement typed API calls for `/api/test-cases`.
- [ ] Run the client tests and verify they pass.

### Task 6: Test Case Library UI

**Files:**
- Create: `frontend/src/testCases/TestCaseForm.tsx`
- Create: `frontend/src/testCases/TestCaseLibraryPage.tsx`
- Create: `frontend/src/testCases/TestCaseLibraryPage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: `TestCaseApi`.
- Produces: module switch, case list, create/edit/delete form, and ordered step add/delete/up/down controls.

- [ ] Write failing UI tests for list, create, edit, delete confirmation, step add/delete/up/down, and switching between Device Library and Test Case Library.
- [ ] Run UI tests and verify failure because the page and navigation are absent.
- [ ] Implement the page and form with accessible labels and buttons; keep Device Library component files untouched.
- [ ] Add simple in-memory module switching in `App` and focused styles for navigation, form, step editor, and table.
- [ ] Run all frontend tests and verify they pass.

### Task 7: Complete verification

**Files:**
- No production files created in this task.

**Interfaces:**
- Verifies the complete Sprint 2 change set and Device Library regression safety.

- [ ] Upgrade a temporary SQLite database to Alembic head and inspect the current revision.
- [ ] Run `python -m pytest backend/tests -q`.
- [ ] Run `npm.cmd test -- --reporter=dot`.
- [ ] Run `npm.cmd run build`.
- [ ] Inspect `git diff`, confirm Device business files are unchanged, and report `git status`.
