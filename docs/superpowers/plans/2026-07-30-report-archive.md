# Report & Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate immutable, versioned HTML test reports from completed runs and create one integrity-checked ZIP archive per report.

**Architecture:** Add a `reports` domain following Router → Schema → Service → Repository → Model. The service captures a complete JSON snapshot, renders deterministic HTML, hashes every generated file, and builds selective archives containing only the report, manifest, and referenced evidence.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, SQLite, Python pathlib/hashlib/zipfile, React, TypeScript, Vitest.

## Global Constraints

- Report and Archive records, snapshots, file paths, and hashes are immutable.
- Only COMPLETED runs whose results are all LOCKED can generate reports.
- One Report can have at most one Archive; a second creation returns HTTP 409.
- Evidence hashes are verified before archive creation.
- Existing Sprint 1–6 core behavior and snapshot mechanisms remain unchanged.
- No PDF, Word templates, AI summaries, email, cloud storage, or BI integration.
- Do not commit during implementation; version solidification is a separate review step.

---

### Task 1: Database and immutable models

**Files:**
- Create: `backend/tests/test_report_migration.py`
- Create: `backend/tests/test_report_models.py`
- Create: `backend/migrations/versions/20260730_0007_report_archive.py`
- Create: `backend/app/models/report.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Produces: `Report` and `Archive` ORM entities with immutable update/delete hooks.

- [ ] Write migration tests for report/archive columns, FKs, version uniqueness, and unique `Archive.report_id`.
- [ ] Run focused tests and confirm failure because revision `20260730_0007` and models do not exist.
- [ ] Implement both ORM entities and Alembic upgrade/downgrade.
- [ ] Run focused tests to green.

### Task 2: Repository and source graph

**Files:**
- Create: `backend/tests/test_report_repository.py`
- Create: `backend/app/reports/__init__.py`
- Create: `backend/app/reports/repository.py`

**Interfaces:**
- Produces: `ReportRepository.get_run_graph`, `next_report_version`, `create_report`, `list_*`, `create_archive`, and `get_archive`.

- [ ] Write repository tests proving sequential report versions, eager-loaded source data, and duplicate archive rejection by database constraint.
- [ ] Run tests and confirm expected missing-module failure.
- [ ] Implement read queries joining Run results, environment snapshot, Evidence, Defect, and Regression without changing existing repositories.
- [ ] Implement transactional create/list/get methods and run focused tests to green.

### Task 3: Snapshot, HTML, and file integrity

**Files:**
- Create: `backend/tests/test_report_snapshot.py`
- Create: `backend/tests/test_report_storage.py`
- Create: `backend/app/reports/snapshots.py`
- Create: `backend/app/reports/renderer.py`
- Create: `backend/app/reports/storage.py`

**Interfaces:**
- Produces: `build_report_snapshot(run, evidences, defects, generated_at)`, `render_report_html(snapshot)`, and `ReportStorage`.

- [ ] Write tests for result counts, defect/regression/evidence capture, old runs without environment snapshots, deterministic escaped HTML, root containment, atomic writes, and SHA256 verification.
- [ ] Run tests and confirm expected failures.
- [ ] Implement snapshot builder using copies of existing snapshots and sorted source records.
- [ ] Implement HTML renderer with standard-library escaping and no external template dependency.
- [ ] Implement local storage with temporary files, atomic replace, open/verify helpers, and run focused tests to green.

### Task 4: Report and archive services

**Files:**
- Create: `backend/tests/test_report_service.py`
- Create: `backend/app/reports/service.py`
- Modify: `backend/app/core/config.py`

**Interfaces:**
- Produces: `ReportService.generate_report`, `create_archive`, `download_report`, and `download_archive`; domain errors map to 404/409.

- [ ] Write tests rejecting incomplete/unlocked runs, preserving old report content after source changes, detecting HTML tampering, verifying Evidence hashes, omitting the database from ZIP, and rejecting a second archive.
- [ ] Run tests and confirm expected failures.
- [ ] Add `report_root` setting and implement report generation with file cleanup on database failure.
- [ ] Implement ZIP manifest generation, evidence verification, selective packaging, and one-archive conflict behavior.
- [ ] Run service tests to green.

### Task 5: API

**Files:**
- Create: `backend/tests/test_report_api.py`
- Create: `backend/app/reports/schemas.py`
- Create: `backend/app/reports/router.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: report generation/list/detail/download and archive create/detail/download endpoints under `/api`.

- [ ] Write API lifecycle tests covering 201, 404, 409, HTML download, ZIP download, and project/run lists.
- [ ] Run tests and confirm 404 route failures.
- [ ] Implement schemas, dependency construction, router, exception handlers, and router registration.
- [ ] Run all backend tests to green.

### Task 6: Frontend Report & Archive workflow

**Files:**
- Create: `frontend/src/reports/types.ts`
- Create: `frontend/src/reports/api.ts`
- Create: `frontend/src/reports/api.test.ts`
- Create: `frontend/src/reports/ReportArchivePage.tsx`
- Create: `frontend/src/reports/ReportArchivePage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`

**Interfaces:**
- Produces: `ReportApi` and a Report & Archive module page.

- [ ] Write tests for project/run selection, readiness display, report version generation, HTML download, archive creation, duplicate conflict display, and ZIP download.
- [ ] Run focused tests and confirm missing-component failures.
- [ ] Implement API client, page state, report/defect/result summaries, and download links.
- [ ] Add navigation without changing existing module behavior and run frontend tests to green.

### Task 7: Full verification

- [ ] Run `python -m pytest backend/tests -q`.
- [ ] Run `npm.cmd test -- --reporter=dot --maxWorkers=1`.
- [ ] Run `npm.cmd run build`.
- [ ] Run migration upgrade/downgrade coverage through the backend suite.
- [ ] Inspect Git diff for Sprint 7-only files and exclude databases, generated reports/archives, `node_modules`, `dist`, caches, and temporary files.
- [ ] Report results without committing or starting further work.
