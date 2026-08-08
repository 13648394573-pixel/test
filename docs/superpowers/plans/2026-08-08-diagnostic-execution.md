# Sprint 8 Diagnostic Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a constrained, auditable ONU Ping diagnostic workflow with adapter matching, retries, layered diagnosis, and Evidence capture while preserving all V1.0.0 history and result-integrity rules.

**Architecture:** Add a new `diagnostics` bounded context that follows Router → Schema → Service → Repository → Model. A persisted `DiagnosticSession` owns append-only `DiagnosticAttempt` records; a single in-process dispatcher executes supported HTTP-form adapters and records raw output as existing RunResult Evidence. Diagnostic output is advisory: it never edits or locks a RunResult.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, SQLite, HTTPX, Pydantic Settings, React 19, TypeScript, Vitest, Testing Library.

## Global Constraints

- Work only in `feature/diagnostic-execution` and its isolated worktree.
- Use test-driven development: migration test first, then models, domain logic, API, frontend, and full regression.
- Do not modify Device, TestCase, Environment, Defect/Regression, Report, or Archive business behavior.
- Do not change `device_snapshot`, `case_snapshot`, `profile_snapshot`, Report Snapshot, or Archive immutability.
- Only a DRAFT RunResult may start a diagnostic or receive diagnostic Evidence.
- Diagnostic output must never update `result`, `actual_result`, `test_notes`, `integrity_status`, or call the lock API.
- Do not implement arbitrary scripts, SSH, configuration delivery, AI, cloud execution, permissions, or a generic workflow engine.
- Adapter credentials come only from environment variables and must never enter the database, logs, response bodies, Snapshot, raw Evidence, or frontend state.
- Preserve the single-machine B/S architecture and use one in-process diagnostic worker; do not add Celery, Redis, or another service.

---

## 1. Final Data Model

### `diagnostic_sessions`

| Field | Type / rule |
|---|---|
| `id` | UUID string primary key |
| `run_result_id` | FK `run_results.id`, `ON DELETE CASCADE`, indexed |
| `retry_of_session_id` | nullable self FK, `ON DELETE RESTRICT` |
| `adapter_key` | string, selected adapter identifier |
| `adapter_version` | string, adapter contract version |
| `wan_mode` | `IPOE` or `PPPOE` |
| `status` | `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `INTERRUPTED` |
| `policy_snapshot` | immutable JSON described below |
| `snapshot_version` | integer, fixed to `1` |
| `error_code` | nullable stable machine-readable code |
| `error_message` | nullable sanitized message; no secrets |
| `created_at` | database timestamp |
| `started_at` | nullable timestamp |
| `completed_at` | nullable timestamp |

`policy_snapshot` version 1 contains only:

```json
{
  "gateway_target": "192.168.1.1",
  "public_ip_target": "1.1.1.1",
  "domain_target": "example.com",
  "packet_count": 3,
  "timeout_seconds": 5,
  "max_attempts_per_layer": 3,
  "layers": ["GATEWAY", "PUBLIC_IP", "DOMAIN"]
}
```

Create a partial unique index for one active session per Result:

```sql
CREATE UNIQUE INDEX uq_diagnostic_sessions_active_result
ON diagnostic_sessions(run_result_id)
WHERE status IN ('PENDING', 'RUNNING');
```

### `diagnostic_attempts`

| Field | Type / rule |
|---|---|
| `id` | UUID string primary key |
| `session_id` | FK `diagnostic_sessions.id`, `ON DELETE CASCADE`, indexed |
| `sequence` | positive integer; unique with `session_id` |
| `layer` | `GATEWAY`, `PUBLIC_IP`, or `DOMAIN` |
| `target` | validated IP address or domain |
| `attempt_number` | positive integer within the layer |
| `status` | `PASS`, `FAIL`, or `ERROR` |
| `packets_sent` / `packets_received` | non-negative integer |
| `loss_percent` | numeric value from 0 through 100 |
| `latency_min_ms` / `latency_avg_ms` / `latency_max_ms` | nullable non-negative numeric values |
| `raw_output` | sanitized text returned by the adapter |
| `error_code` | nullable adapter error code |
| `started_at` / `finished_at` | timestamps |

Attempts are append-only. The worker creates a complete Attempt after each call; no API updates or deletes an Attempt.

### `diagnostic_attempt_evidences`

- Composite primary key: `(diagnostic_attempt_id, evidence_id)`.
- FK Attempt and Evidence with `ON DELETE CASCADE`.
- Evidence remains owned by the same DRAFT RunResult under the V1.0.0 exactly-one-owner rule.
- Sprint 8 does not implement multi-Result Evidence; that remains Sprint 10 scope.

## 2. API Contract

### Start diagnostic

`POST /api/run-results/{result_id}/diagnostics` → `202 Accepted`

```json
{
  "wan_mode": "IPOE",
  "adapter_key": null,
  "gateway_target": "192.168.1.1",
  "public_ip_target": "1.1.1.1",
  "domain_target": "example.com",
  "packet_count": 3,
  "timeout_seconds": 5,
  "max_attempts_per_layer": 3
}
```

- `adapter_key=null` invokes registry matching against immutable Device Snapshot.
- Explicit adapter keys must still support that Device Snapshot.
- Response is the persisted Session with an empty attempts list.

### Query

- `GET /api/run-results/{result_id}/diagnostics` → session history, newest first.
- `GET /api/diagnostics/{session_id}` → session, ordered attempts, linked Evidence.

### Retry

`POST /api/diagnostics/{session_id}/retry` → `202 Accepted`

- Only `COMPLETED`, `FAILED`, or `INTERRUPTED` may be retried.
- Creates a new Session using the original immutable policy and sets `retry_of_session_id`.
- Never mutates the source Session or Attempts.

### Error mapping

| HTTP | Condition |
|---:|---|
| 404 | Result or Session not found |
| 409 | Result LOCKED, another active Session exists, or retry source not terminal |
| 422 | invalid target/policy, no supporting adapter, or explicit adapter mismatch |
| 503 | dispatcher is unavailable before enqueue; persisted Session becomes `FAILED` |

## 3. Adapter Interface

Create a narrow contract in `backend/app/diagnostics/contracts.py`:

```python
@dataclass(frozen=True)
class DiagnosticContext:
    device_snapshot: Mapping[str, Any]
    environment_snapshot: Mapping[str, Any] | None
    wan_mode: Literal["IPOE", "PPPOE"]


@dataclass(frozen=True)
class PingRequest:
    layer: Literal["GATEWAY", "PUBLIC_IP", "DOMAIN"]
    target: str
    packet_count: int
    timeout_seconds: int


@dataclass(frozen=True)
class PingObservation:
    status: Literal["PASS", "FAIL", "ERROR"]
    packets_sent: int
    packets_received: int
    loss_percent: Decimal
    latency_min_ms: Decimal | None
    latency_avg_ms: Decimal | None
    latency_max_ms: Decimal | None
    raw_output: str
    error_code: str | None = None


class PingAdapter(Protocol):
    key: str
    version: str

    def supports(self, device_snapshot: Mapping[str, Any]) -> bool: ...
    def ping(
        self,
        context: DiagnosticContext,
        request: PingRequest,
    ) -> PingObservation: ...
```

The first production adapter is `HttpFormPingAdapter`. It accepts a strictly validated local JSON definition with vendor/model/version matchers, relative login/start/poll paths, fixed GET/POST methods, form-field names, WAN value mapping, completion markers, and result regexes. It must not accept executable code, shell commands, absolute operation URLs, arbitrary headers, or custom Python imports.

Adapter configuration:

- `TEST_WORKBENCH_DIAGNOSTIC_ADAPTER_CONFIG=./config/diagnostic-adapters.json`
- `TEST_WORKBENCH_DIAGNOSTIC_<ADAPTER_KEY>_USERNAME`
- `TEST_WORKBENCH_DIAGNOSTIC_<ADAPTER_KEY>_PASSWORD`

The management base URL is read from the Run Environment Snapshot parameter `onu_management_url`. The service accepts only `http`/`https` URLs whose resolved address is loopback, link-local, or RFC1918; redirects to public addresses are rejected.

## 4. Testing Strategy

- Migration: upgrade from revision `20260730_0007`, constraints, indexes, cascade, and downgrade.
- Models: immutable policy, append-only Attempts, valid status/layer/WAN checks.
- Adapter contract: registry precedence, explicit mismatch, HTTP login, WAN mapping, polling, parsing, timeout, redaction, SSRF/redirect rejection.
- Service: DRAFT-only creation, active-session conflict, layered short-circuiting, retry counts, terminal states, restart interruption, no Result mutation.
- Evidence: raw output stored as sanitized `LOG`, hash valid, Attempt link valid, cleanup on failure.
- API: 202/404/409/422/503 contracts and response ordering.
- Frontend: create, poll, render layers/attempts/evidence, retry terminal session, locked read-only behavior.
- Regression: all backend tests, frontend tests with one worker, and production build.
- Real device acceptance: supported ONU completes IPoE and PPPoE diagnostics without exposing credentials; unsupported firmware fails safely and leaves manual workflow available.

## 5. Acceptance Criteria

1. A DRAFT Result can start IPoE or PPPoE Ping diagnostics and receives `202`.
2. Registry auto-selects a matching adapter; unsupported or mismatched adapters return `422` before network access.
3. Each layer runs no more than three attempts and records every completed observation append-only.
4. Gateway failure stops public-IP/domain execution and produces a clear layered diagnosis; public-IP failure stops domain execution; domain failure is recorded separately.
5. Each Attempt creates a sanitized LOG Evidence linked to both the Attempt and its owning RunResult.
6. Diagnostic processing never changes or locks RunResult fields.
7. LOCKED Result rejects new and retried diagnostics with `409`.
8. Restart converts persisted `RUNNING` sessions to `INTERRUPTED`; it never silently resumes network actions.
9. Existing 117 backend tests, all frontend tests, and production build pass.
10. Upgrade/downgrade leaves all pre-Sprint-8 tables and V1.0.0 artifacts intact.

## 6. Risk Controls

| Risk | Control |
|---|---|
| Firmware/UI incompatibility | Explicit support matcher and sanitized fixture per adapter; no best-effort unknown-device execution |
| False PASS/FAIL | Preserve attempts and raw output; diagnostic is advisory and cannot set Result |
| Duplicate execution | Partial unique active-session index plus service conflict check |
| Process restart | Persist state; mark stale RUNNING sessions INTERRUPTED at startup |
| Credential leakage | Environment-only credentials; request/response redaction tests; never return credential-bearing payloads |
| SSRF | Private management URL validation, DNS resolution check, relative operation paths, redirect validation |
| Evidence/file inconsistency | Write through existing EvidenceStorage; rollback metadata and delete file on transaction failure |
| Long-running request | Return 202 and execute through one in-process worker; frontend polls terminal state |
| Scope expansion | Fixed Ping contract only; reject shell commands, arbitrary scripts, SSH, config delivery, and plugin imports |

---

### Task 1: Migration contract and diagnostic models

**Files:**
- Create: `backend/tests/test_diagnostic_migration.py`
- Create: `backend/tests/test_diagnostic_models.py`
- Create: `backend/migrations/versions/20260808_0008_diagnostic_execution.py`
- Create: `backend/app/models/diagnostic.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Produces: `DiagnosticSession`, `DiagnosticAttempt`, and `DiagnosticAttemptEvidence` ORM models.
- Consumes: existing `RunResult` and `Evidence` identifiers without modifying their domain behavior.

- [ ] **Step 1: Write failing migration tests** for upgrade from `20260730_0007`, all columns/checks/FKs, the active-session partial unique index, Attempt sequence uniqueness, Evidence links, cascades, and downgrade back to `20260730_0007`.
- [ ] **Step 2: Run the migration test and verify RED.**

  Run: `python -m pytest backend/tests/test_diagnostic_migration.py -q`

  Expected: FAIL because revision `20260808_0008` and its tables do not exist.

- [ ] **Step 3: Implement the Alembic revision** with explicit named constraints and reverse-order downgrade.
- [ ] **Step 4: Run the migration test and verify GREEN.**

  Run: `python -m pytest backend/tests/test_diagnostic_migration.py -q`

  Expected: PASS.

- [ ] **Step 5: Write failing ORM tests** proving policy mutation, Attempt updates/deletes, invalid states, duplicate active sessions, and duplicate sequence values are rejected.
- [ ] **Step 6: Implement the three ORM models** and SQLAlchemy immutability listeners following the existing Snapshot and Evidence patterns.
- [ ] **Step 7: Run focused model and migration tests.**

  Run: `python -m pytest backend/tests/test_diagnostic_models.py backend/tests/test_diagnostic_migration.py -q`

  Expected: PASS.

- [ ] **Step 8: Commit.**

  ```powershell
  git add backend/app/models backend/migrations/versions/20260808_0008_diagnostic_execution.py backend/tests/test_diagnostic_migration.py backend/tests/test_diagnostic_models.py
  git commit -m "feat(diagnostic): add diagnostic persistence model"
  ```

### Task 2: Adapter contracts, configuration, and registry

**Files:**
- Create: `backend/app/diagnostics/__init__.py`
- Create: `backend/app/diagnostics/contracts.py`
- Create: `backend/app/diagnostics/config.py`
- Create: `backend/app/diagnostics/registry.py`
- Create: `backend/tests/test_diagnostic_registry.py`
- Modify: `backend/app/core/config.py`

**Interfaces:**
- Produces: `PingAdapter`, `DiagnosticContext`, `PingRequest`, `PingObservation`, `DiagnosticAdapterRegistry.match(device_snapshot, explicit_key=None)`.
- Consumes: Device and Environment Snapshot mappings only; never ORM entities.

- [ ] **Step 1: Write failing contract and registry tests** for automatic matching, exact explicit-key lookup, mismatch rejection, duplicate keys, deterministic first match, missing adapter, and Snapshot non-mutation.
- [ ] **Step 2: Run the tests and verify RED.**

  Run: `python -m pytest backend/tests/test_diagnostic_registry.py -q`

  Expected: FAIL because the diagnostics package is absent.

- [ ] **Step 3: Implement immutable dataclasses, the Protocol, typed adapter configuration models, and registry.**
- [ ] **Step 4: Add Settings fields** for adapter-config path, worker enabled flag, and polling interval; do not add credential fields to Settings.
- [ ] **Step 5: Run focused tests and verify GREEN.**

  Run: `python -m pytest backend/tests/test_diagnostic_registry.py backend/tests/test_config.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit.**

  ```powershell
  git add backend/app/diagnostics backend/app/core/config.py backend/tests/test_diagnostic_registry.py backend/tests/test_config.py
  git commit -m "feat(diagnostic): define ping adapter contract"
  ```

### Task 3: Constrained HTTP-form adapter

**Files:**
- Create: `backend/app/diagnostics/adapters/__init__.py`
- Create: `backend/app/diagnostics/adapters/http_form.py`
- Create: `backend/app/diagnostics/redaction.py`
- Create: `backend/tests/fixtures/diagnostics/http_form_adapter.json`
- Create: `backend/tests/fixtures/diagnostics/login_success.html`
- Create: `backend/tests/fixtures/diagnostics/ping_pending.html`
- Create: `backend/tests/fixtures/diagnostics/ping_complete.html`
- Create: `backend/tests/test_http_form_ping_adapter.py`
- Modify: `backend/pyproject.toml`

**Interfaces:**
- Produces: `HttpFormPingAdapter.ping(context, request) -> PingObservation`.
- Consumes: validated adapter definition, environment-only credentials, and private `onu_management_url`.

- [ ] **Step 1: Add HTTPX to production dependencies** with `httpx>=0.28,<1`; do not install it during planning.
- [ ] **Step 2: Write failing adapter tests** using `httpx.MockTransport` for login, cookies, IPOE/PPPOE form values, poll completion, PASS/FAIL parsing, timeout, malformed response, credential redaction, relative-path enforcement, private-address validation, DNS rebinding check, and public redirect rejection.
- [ ] **Step 3: Run tests and verify RED.**

  Run: `python -m pytest backend/tests/test_http_form_ping_adapter.py -q`

  Expected: FAIL because the adapter is absent.

- [ ] **Step 4: Implement the adapter** with only GET/POST operations, bounded polling, resolved-address validation before every request, and sanitized raw output capped at 64 KiB.
- [ ] **Step 5: Run focused tests and verify GREEN.**

  Run: `python -m pytest backend/tests/test_http_form_ping_adapter.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit.**

  ```powershell
  git add backend/app/diagnostics/adapters backend/app/diagnostics/redaction.py backend/tests/fixtures/diagnostics backend/tests/test_http_form_ping_adapter.py backend/pyproject.toml
  git commit -m "feat(diagnostic): add constrained http ping adapter"
  ```

### Task 4: Repository and layered diagnostic service

**Files:**
- Create: `backend/app/diagnostics/repository.py`
- Create: `backend/app/diagnostics/service.py`
- Create: `backend/app/diagnostics/policy.py`
- Create: `backend/tests/test_diagnostic_repository.py`
- Create: `backend/tests/test_diagnostic_service.py`

**Interfaces:**
- Produces: `DiagnosticService.create`, `get`, `list_for_result`, `retry`, `execute`, and `interrupt_stale_sessions`.
- Consumes: `DiagnosticAdapterRegistry`, existing TestExecution repository lookups, Evidence service, and a clock callable.

- [ ] **Step 1: Write failing repository tests** for create/get/list ordering, atomic status transitions, append-only Attempt insertion, active-session conflict, linked Evidence, and stale-RUNNING interruption.
- [ ] **Step 2: Write failing service tests** for DRAFT-only creation, policy validation, adapter selection, retry provenance, layered stopping rules, maximum attempts, terminal status, adapter errors, and zero mutation of RunResult fields.
- [ ] **Step 3: Run focused tests and verify RED.**

  Run: `python -m pytest backend/tests/test_diagnostic_repository.py backend/tests/test_diagnostic_service.py -q`

  Expected: FAIL because repository and service are absent.

- [ ] **Step 4: Implement policy validation** with `ipaddress`, strict domain validation, packet count `1..5`, timeout `1..30`, and max attempts `1..3`.
- [ ] **Step 5: Implement repository transitions** using fresh database reads before every state change.
- [ ] **Step 6: Implement layered execution** so GATEWAY failure stops later layers, PUBLIC_IP failure stops DOMAIN, and every adapter call creates a complete append-only Attempt.
- [ ] **Step 7: Run focused tests and verify GREEN.**

  Run: `python -m pytest backend/tests/test_diagnostic_repository.py backend/tests/test_diagnostic_service.py -q`

  Expected: PASS.

- [ ] **Step 8: Commit.**

  ```powershell
  git add backend/app/diagnostics backend/tests/test_diagnostic_repository.py backend/tests/test_diagnostic_service.py
  git commit -m "feat(diagnostic): implement layered diagnostic service"
  ```

### Task 5: Diagnostic Evidence capture

**Files:**
- Create: `backend/app/diagnostics/evidence.py`
- Create: `backend/tests/test_diagnostic_evidence.py`
- Modify: `backend/app/diagnostics/service.py`

**Interfaces:**
- Produces: `DiagnosticEvidenceRecorder.record(attempt, run_result, observation) -> Evidence`.
- Consumes: existing `EvidenceStorage`, `EvidenceRepository`, and DRAFT lifecycle rules.

- [ ] **Step 1: Write failing tests** for one LOG file per Attempt, sanitized text, SHA256 correctness, Attempt/Evidence link creation, DRAFT ownership, file cleanup on DB failure, and rejection if the Result becomes LOCKED during execution.
- [ ] **Step 2: Run tests and verify RED.**

  Run: `python -m pytest backend/tests/test_diagnostic_evidence.py -q`

  Expected: FAIL because the recorder is absent.

- [ ] **Step 3: Implement deterministic Evidence content** containing session ID, layer, target, packet statistics, timestamps, and sanitized raw output; use filenames such as `diagnostic-GATEWAY-01.txt`.
- [ ] **Step 4: Integrate recording after each Attempt** in the same service boundary; if the Result was locked concurrently, terminate the Session as `FAILED` with `RESULT_LOCKED` and do not write another file.
- [ ] **Step 5: Run Evidence and diagnostic service tests.**

  Run: `python -m pytest backend/tests/test_diagnostic_evidence.py backend/tests/test_diagnostic_service.py backend/tests/test_evidence_service.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit.**

  ```powershell
  git add backend/app/diagnostics/evidence.py backend/app/diagnostics/service.py backend/tests/test_diagnostic_evidence.py
  git commit -m "feat(diagnostic): capture diagnostic evidence"
  ```

### Task 6: Persisted dispatcher and application lifecycle

**Files:**
- Create: `backend/app/diagnostics/dispatcher.py`
- Create: `backend/tests/test_diagnostic_dispatcher.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: `DiagnosticDispatcher.start()`, `enqueue(session_id)`, and `shutdown()`.
- Consumes: application `session_factory` and a service factory that creates one DiagnosticService per worker transaction.

- [ ] **Step 1: Write failing dispatcher tests** for FIFO execution, one worker only, enqueue after persistence, unavailable dispatcher, graceful shutdown, worker exception isolation, and startup interruption of stale RUNNING sessions.
- [ ] **Step 2: Run tests and verify RED.**

  Run: `python -m pytest backend/tests/test_diagnostic_dispatcher.py -q`

  Expected: FAIL because dispatcher is absent.

- [ ] **Step 3: Implement a bounded `queue.Queue` and one daemon worker thread**; each job opens and closes its own SQLAlchemy Session.
- [ ] **Step 4: Wire dispatcher into FastAPI lifespan** after database initialization and shut it down before engine disposal. Startup must call `interrupt_stale_sessions` and must not re-enqueue interrupted work.
- [ ] **Step 5: Run lifecycle and dispatcher tests.**

  Run: `python -m pytest backend/tests/test_diagnostic_dispatcher.py backend/tests/test_health.py backend/tests/test_database.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit.**

  ```powershell
  git add backend/app/diagnostics/dispatcher.py backend/app/main.py backend/tests/test_diagnostic_dispatcher.py
  git commit -m "feat(diagnostic): add persisted diagnostic dispatcher"
  ```

### Task 7: Diagnostic API

**Files:**
- Create: `backend/app/diagnostics/schemas.py`
- Create: `backend/app/diagnostics/router.py`
- Create: `backend/tests/test_diagnostic_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: the four endpoints defined in section 2 and stable exception-to-HTTP mappings.
- Consumes: `DiagnosticService` and `DiagnosticDispatcher`; routers contain no business decisions.

- [ ] **Step 1: Write failing API tests** for 202 creation/retry, ordered queries, complete Attempt/Evidence response, validation, 404, 409, 422, 503, and credential absence in serialized responses.
- [ ] **Step 2: Run tests and verify RED.**

  Run: `python -m pytest backend/tests/test_diagnostic_api.py -q`

  Expected: FAIL because routes are absent.

- [ ] **Step 3: Implement Pydantic schemas and Router → Service calls**; enqueue only after the creation transaction commits.
- [ ] **Step 4: Register router and exception handlers** under the existing `/api` prefix.
- [ ] **Step 5: Run API and existing execution/evidence tests.**

  Run: `python -m pytest backend/tests/test_diagnostic_api.py backend/tests/test_test_execution_api.py backend/tests/test_evidence_api.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit.**

  ```powershell
  git add backend/app/diagnostics/schemas.py backend/app/diagnostics/router.py backend/app/main.py backend/tests/test_diagnostic_api.py
  git commit -m "feat(diagnostic): expose diagnostic execution api"
  ```

### Task 8: Frontend Diagnostic panel

**Files:**
- Create: `frontend/src/diagnostics/types.ts`
- Create: `frontend/src/diagnostics/api.ts`
- Create: `frontend/src/diagnostics/api.test.ts`
- Create: `frontend/src/diagnostics/DiagnosticPanel.tsx`
- Create: `frontend/src/diagnostics/DiagnosticPanel.test.tsx`
- Modify: `frontend/src/testExecution/ResultEditor.tsx`
- Modify: `frontend/src/testExecution/ResultEditor.test.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Produces: `DiagnosticApi` and `DiagnosticPanel` for one RunResult.
- Consumes: Result ID, integrity status, existing Evidence download URL, and polling-safe Session responses.

- [ ] **Step 1: Write failing API client tests** for create/list/get/retry requests, 202 JSON parsing, and detail error propagation.
- [ ] **Step 2: Write failing component tests** for adapter-auto mode, IPOE/PPPOE selection, start, one-second polling, layered Attempt table, Evidence links, terminal retry, error rendering, unmount cancellation, and LOCKED read-only state.
- [ ] **Step 3: Run frontend tests and verify RED.**

  Run: `npm.cmd test -- --reporter=dot --maxWorkers=1 frontend/src/diagnostics frontend/src/testExecution/ResultEditor.test.tsx`

  Expected: FAIL because diagnostic frontend files are absent.

- [ ] **Step 4: Implement typed API and panel**; stop polling at terminal status and never infer or write PASS/FAIL into ResultEditor.
- [ ] **Step 5: Mount DiagnosticPanel inside each ResultEditor** above the existing Evidence section; keep all existing manual result controls unchanged.
- [ ] **Step 6: Run focused frontend tests and verify GREEN.**

  Run: `npm.cmd test -- --reporter=dot --maxWorkers=1 frontend/src/diagnostics frontend/src/testExecution/ResultEditor.test.tsx`

  Expected: PASS.

- [ ] **Step 7: Commit.**

  ```powershell
  git add frontend/src/diagnostics frontend/src/testExecution/ResultEditor.tsx frontend/src/testExecution/ResultEditor.test.tsx frontend/src/index.css
  git commit -m "feat(diagnostic): add diagnostic execution panel"
  ```

### Task 9: Full validation and Sprint documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/API.md`
- Modify: `docs/DATABASE.md`
- Create: `docs/SPRINT_8_DIAGNOSTIC_EXECUTION.md`

**Interfaces:**
- Produces: operator setup, supported-adapter format, API/database documentation, verification evidence, and explicit unsupported-device behavior.
- Consumes: final backend and frontend contracts from Tasks 1–8.

- [ ] **Step 1: Document local adapter configuration and credential environment variables** using non-secret examples.
- [ ] **Step 2: Document migration `20260808_0008`, tables, invariants, APIs, worker restart behavior, and manual fallback.**
- [ ] **Step 3: Run the empty-database migration test.**

  Run: `python -m pytest backend/tests/test_diagnostic_migration.py -q`

  Expected: PASS, including upgrade and downgrade.

- [ ] **Step 4: Run all backend tests.**

  Run: `python -m pytest backend/tests -q`

  Expected: all tests pass with zero failures.

- [ ] **Step 5: Run all frontend tests with bounded workers.**

  Run: `npm.cmd test -- --reporter=dot --maxWorkers=1`

  Expected: all tests pass with zero failures.

- [ ] **Step 6: Run production build.**

  Run: `npm.cmd run build`

  Expected: TypeScript and Vite build succeed.

- [ ] **Step 7: Run real-device acceptance** for one supported ONU: IPOE and PPPOE, gateway/public-IP/domain layers, retry evidence, credential redaction, and manual fallback after an unsupported adapter test.
- [ ] **Step 8: Verify repository scope.**

  Run: `git diff --check` and `git status --short`

  Expected: no database files, Evidence artifacts, credentials, `node_modules`, `dist`, cache, or temporary files.

- [ ] **Step 9: Commit documentation.**

  ```powershell
  git add README.md docs/API.md docs/DATABASE.md docs/SPRINT_8_DIAGNOSTIC_EXECUTION.md
  git commit -m "docs: document sprint 8 diagnostic execution"
  ```

## Plan Self-Review

- Scope coverage: migration, model, Adapter, Retry, layered diagnosis, Evidence, API, frontend, real-device acceptance, and full regression are mapped to Tasks 1–9.
- Historical integrity: no task updates Snapshot or LOCKED Result fields; diagnostic state is isolated and additive.
- Dependency control: only HTTPX moves into production dependencies; no browser engine, task broker, or external service is introduced.
- Completeness scan: every task names its concrete deliverable; adapter behavior is driven by a strict declarative schema rather than undocumented vendor code.
- Type consistency: Session/Attempt states, layers, WAN modes, adapter contracts, and endpoint names are consistent throughout the plan.
