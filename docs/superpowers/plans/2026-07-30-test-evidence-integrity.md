# Sprint 5 Test Evidence & Result Integrity Implementation Plan

> Work only in `feature/test-evidence-integrity`. Preserve Device and Test Case
> behavior, and do not implement environment, reporting, automation, AI, or
> permissions.

**Goal:** Add auditable draft/locked test results and local evidence management
for run results and defects.

**Architecture:** Keep the existing Router → Schema → Service → Repository →
Model flow. Add an Evidence aggregate service for metadata and filesystem
coordination. Result locking remains in Test Execution; Defect/Regression
services consume only locked results. SQLite foreign-key enforcement is enabled
on every application-created connection.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, SQLite, React, TypeScript,
Vitest, Testing Library.

---

## Task 1: Migration and database contracts

**Files:**
- Create: `backend/tests/test_evidence_integrity_migration.py`
- Create: `backend/migrations/versions/20260730_0005_result_integrity_evidence.py`
- Modify: `backend/tests/test_database.py`
- Modify: `backend/app/db/session.py`

1. Add failing migration tests for the new RunResult columns, legacy-data
   backfill, Evidence table constraints/indexes, downgrade, and cascade
   enforcement.
2. Add a failing database test proving `PRAGMA foreign_keys=1` on connections
   created by the application.
3. Run only these tests and confirm failures are caused by the missing migration
   and pragma.
4. Implement the migration and connection event, then rerun until green.

## Task 2: Result integrity domain

**Files:**
- Modify: `backend/tests/test_test_execution_repository.py`
- Modify: `backend/tests/test_test_execution_service.py`
- Modify: `backend/tests/test_test_execution_api.py`
- Modify: `backend/app/models/test_execution.py`
- Modify: `backend/app/test_execution/repository.py`
- Modify: `backend/app/test_execution/service.py`
- Modify: `backend/app/test_execution/schemas.py`
- Modify: `backend/app/test_execution/router.py`
- Modify: `backend/app/main.py`

1. Add failing tests for DRAFT creation, draft field updates, lock validation,
   one-way locking, snapshot immutability, and run completion only after every
   result is locked.
2. Add `integrity_status`, `actual_result`, `blocked_reason`, `test_notes`, and
   `locked_at` to RunResult.
3. Replace result-only updates with draft payload updates and add a lock
   operation. Enforce FAIL actual-result and BLOCKED reason requirements, and
   reject locked-result changes with HTTP 409.
4. Run focused Test Execution tests until green.

## Task 3: Evidence metadata and local storage

**Files:**
- Create: `backend/tests/test_evidence_repository.py`
- Create: `backend/tests/test_evidence_storage.py`
- Create: `backend/tests/test_evidence_service.py`
- Create: `backend/tests/test_evidence_api.py`
- Create: `backend/app/models/evidence.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/evidence/__init__.py`
- Create: `backend/app/evidence/repository.py`
- Create: `backend/app/evidence/storage.py`
- Create: `backend/app/evidence/service.py`
- Create: `backend/app/evidence/schemas.py`
- Create: `backend/app/evidence/router.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/pyproject.toml`

1. Add failing tests for exactly-one-owner metadata, immutable metadata, UUID
   relative paths, streamed size/hash calculation, maximum size, containment,
   atomic cleanup, missing-file handling, and API response codes.
2. Implement Evidence with RunResult/Defect ownership, category, file metadata,
   checksum, description, and timestamps.
3. Implement local streaming storage under the configured evidence root.
4. Implement list/upload/download/delete APIs. RunResult evidence is mutable
   only while DRAFT. Defect evidence follows:
   - OPEN / IN_PROGRESS / REOPENED: add and delete
   - RESOLVED: add only
   - CLOSED: read only
5. Add multipart support and run focused Evidence tests until green.

## Task 4: Defect and regression integrity integration

**Files:**
- Modify: `backend/tests/test_defect_service.py`
- Modify: `backend/tests/test_defect_api.py`
- Modify: `backend/app/defects/service.py`

1. Add failing tests proving defect creation and regression creation reject
   DRAFT results even when those results contain FAIL or BLOCKED values.
2. Require `integrity_status=LOCKED` in both service paths without changing the
   existing defect state machine or historical snapshots.
3. Run focused Defect tests until green.

## Task 5: Frontend result details and evidence

**Files:**
- Modify: `frontend/src/testExecution/types.ts`
- Modify: `frontend/src/testExecution/api.ts`
- Modify: `frontend/src/testExecution/api.test.ts`
- Modify: `frontend/src/testExecution/TestExecutionPage.tsx`
- Modify: `frontend/src/testExecution/TestExecutionPage.test.tsx`
- Modify: `frontend/src/defects/types.ts`
- Modify: `frontend/src/defects/api.ts`
- Modify: `frontend/src/defects/api.test.ts`
- Modify: `frontend/src/defects/DefectPage.tsx`
- Modify: `frontend/src/defects/DefectPage.test.tsx`
- Modify: `frontend/src/index.css`

1. Add failing API and component tests for draft fields, save, lock confirmation,
   locked read-only state, evidence upload/download/delete, and defect lifecycle
   controls.
2. Extend API contracts with multipart evidence calls and result lock calls.
3. Add compact result editing and attachment controls to Test Execution.
4. Add evidence controls to Defect detail, including RESOLVED add-only and
   CLOSED read-only behavior.
5. Run focused frontend tests until green.

## Task 6: Full verification and scope audit

1. Run `python -m pytest backend/tests -q`.
2. Run `npm.cmd test -- --reporter=dot --maxWorkers=1`.
3. Run `npm.cmd run build`.
4. Inspect `git diff --check`, changed-file list, ignored artifacts, and
   `git status`.
5. Confirm no database, evidence payload, node_modules, dist, cache, or temporary
   files are tracked. Do not commit or merge.
