# ONU Registration and Dual WAN Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first real ONU Test Skill that registers an ONU on a Huawei MA5800-X7, provisions and independently verifies IPoE and PPPoE WAN connectivity, and produces six auditable screenshot evidence groups.

**Architecture:** Extend the Sprint 0 Test Intelligence and Execution Foundation instead of creating a parallel script system. A deterministic DRAFT catalog defines the Skill and standards; allow-listed local Runner actions perform MA5800, ONU Web, and PC probes; a resumable coordinator advances one action or operator interaction at a time and persists events, observations, evidence, and recovery state.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x, Alembic, SQLite, Paramiko, Playwright, Pillow, keyring, Pytest; React 19, TypeScript, Vite, Vitest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-18-onu-registration-dual-wan-skill-design.md`

## Global Constraints

- Implement only `ONU_REGISTRATION_DUAL_WAN_CONNECTIVITY` version `1.0.0`; do not add VLAN binding, QoS, IPv6, TR069, other OLT vendors, AI, cloud, or multi-user features.
- Support Huawei MA5800-X7 only in the first adapter.
- Keep the Skill, Standard, Standard Profile, and Runner Plugin in DRAFT/DEVELOPMENT until real PASS, FAIL, and BLOCKED lab runs are recorded.
- Persist six logical evidence groups: E1 autofind, E2 registration, E3 IPoE address, E4 IPoE Ping, E5 PPPoE address, E6 PPPoE Ping.
- E3 and E5 require both OLT `wan-info` and ONU Web WAN evidence; E4 and E6 require ONU Ping plus PC-side evidence or an explicit operator record.
- Never store OLT, ONU, or PPPoE secret values in database fields, logs, screenshots, events, reports, fixtures, or Git.
- Never accept arbitrary OLT command text from an API, UI, Skill parameter, database row, or operator interaction.
- Require operator confirmation before deleting registration, clearing WAN/service-port state, switching the active WAN, restoring configuration, or keeping a changed configuration.
- Default to sequential isolated WAN testing; concurrent dual-WAN mode and customer-simplified evaluation must be explicit execution snapshot values.
- All execution remains local and must not download code, standards, or Runner packages at runtime.
- Preserve all V1 Test Management behavior and migration compatibility.

## File Structure

### Backend domains

- `backend/app/skill_catalog/definitions.py`: frozen catalog DTOs shared by deterministic seed definitions.
- `backend/app/skill_catalog/onu_registration_dual_wan.py`: the exact DRAFT Skill, Standard, Test Case, evidence rules, actions, and bindings.
- `backend/app/skill_catalog/repository.py`: idempotent catalog lookup and persistence.
- `backend/app/skill_catalog/service.py`: install and read-only catalog operations.
- `backend/app/skill_catalog/schemas.py`: Skill summary/detail API schemas.
- `backend/app/skill_catalog/router.py`: list/detail/install-DRAFT endpoints.
- `backend/app/local_runner/contracts.py`: action context, outcome, observation, artifact, and credential protocols.
- `backend/app/local_runner/registry.py`: in-process allow-list keyed by plugin/action code.
- `backend/app/local_runner/credentials.py`: keyring-backed credential resolver and fake-friendly protocol.
- `backend/app/local_runner/credential_router.py`: local-only credential enrollment/status/delete API with no secret echo.
- `backend/app/local_runner/evidence.py`: redaction, safe artifact writing, SHA256, and terminal PNG rendering.
- `backend/app/local_runner/ma5800/parsers.py`: pure autofind, ONT, WAN, service-port, prompt, and error parsing.
- `backend/app/local_runner/ma5800/transport.py`: Paramiko shell transport with paging and `<cr>` handling.
- `backend/app/local_runner/ma5800/actions.py`: allow-listed command builders and MA5800 action handlers.
- `backend/app/local_runner/onu_web/contracts.py`: product adapter protocol and observations.
- `backend/app/local_runner/onu_web/selectors.py`: code-owned selector profiles keyed by ONU firmware family.
- `backend/app/local_runner/onu_web/neutral.py`: Playwright WAN/Ping capture for the current neutral ONU firmware family.
- `backend/app/local_runner/pc_probe.py`: interface-aware Ping/DNS/HTTP observations without changing global routing.
- `backend/app/skill_execution/repository.py`: Run/Result/Session/Event/Interaction/Evidence persistence.
- `backend/app/skill_execution/evaluator.py`: Standard-bound PASS/FAIL/BLOCKED and evidence completeness evaluation.
- `backend/app/skill_execution/coordinator.py`: resumable sequential/concurrent workflow.
- `backend/app/skill_execution/service.py`: application service and recovery boundary.
- `backend/app/skill_execution/schemas.py`: request and execution-view API schemas.
- `backend/app/skill_execution/router.py`: create, advance, respond, evidence, and view endpoints.

### Database and existing integration

- `backend/app/models/evidence.py`: add immutable execution/step/capture metadata.
- `backend/app/models/execution_session.py`: add structured operator request/response metadata.
- `backend/app/models/test_execution.py`: allow one-time sealing of V2 derived result snapshots before LOCKED.
- `backend/app/models/__init__.py`: export any new model types.
- `backend/migrations/versions/20260918_0021_skill_evidence_metadata.py`: additive metadata migration.
- `backend/app/core/config.py`: local Runner and keyring settings without secret values.
- `backend/app/main.py`: register routers, action registry, and startup recovery scan.
- `backend/pyproject.toml`: declare Paramiko, Pillow, and keyring runtime dependencies.

### Frontend

- `frontend/src/skillExecution/types.ts`: catalog, configuration, session, evidence, and interaction types.
- `frontend/src/skillExecution/api.ts`: Skill and execution endpoints.
- `frontend/src/skillExecution/SkillExecutionPage.tsx`: first-Skill execution wizard and timeline.
- `frontend/src/skillExecution/SkillConfigurationForm.tsx`: mode, standard, environment, target, and end-policy form.
- `frontend/src/skillExecution/OperatorInteractionDialog.tsx`: risk/impact confirmation UI.
- `frontend/src/skillExecution/EvidenceGrid.tsx`: E1–E6 completeness and preview.
- `frontend/src/App.tsx`: add the “测试能力” module without changing V1 pages.
- `frontend/src/index.css`: focused styles for the new page and dialog.

### Packaging and docs

- `scripts/build-offline-bundle.ps1`: build backend wheelhouse, Playwright browser bundle, frontend static assets, and checksummed manifest.
- `scripts/install-local.ps1`: preflight, venv, bundled dependency/browser install, migration, and shortcut creation.
- `scripts/start-workbench.ps1`: migration guard, backend launch, readiness check, and browser open.
- `Start ONU Test Workbench.cmd`: double-click entrypoint.
- `docs/ONU_REGISTRATION_DUAL_WAN_LAB_RUNBOOK.md`: operator-safe lab validation sequence.
- `docs/ONU_REGISTRATION_DUAL_WAN_SKILL.md`: user-facing parameter, evidence, and verdict guide.

---

### Task 1: Add execution evidence and operator metadata

**Files:**
- Modify: `backend/app/models/evidence.py`
- Modify: `backend/app/models/execution_session.py`
- Modify: `backend/app/models/test_execution.py`
- Create: `backend/migrations/versions/20260918_0021_skill_evidence_metadata.py`
- Create: `backend/tests/test_skill_evidence_metadata_migration.py`
- Modify: `backend/tests/test_execution_session_models.py`
- Modify: `backend/tests/test_test_execution_service.py`

**Interfaces:**
- Produces `Evidence.execution_session_id`, `step_ref`, `capture_method`, and `redacted`.
- Produces `OperatorInteraction.interaction_type`, `risk_level`, `options_json`, `impact_preview`, and `response_json`.
- Produces `seal_result_derived_snapshots(result, *, observations, matched_rule_codes, standard_evaluations, evidence_validation)` with one-write semantics.

- [ ] **Step 1: Write failing model and migration tests**

```python
def test_generated_evidence_records_step_and_redaction(db_session):
    evidence = Evidence(
        run_result_id="result-1",
        execution_session_id="session-1",
        step_ref="IPOE_ADDRESS",
        evidence_rule_code="E3_IPOE_ADDRESS",
        capture_method="OLT_RENDER",
        redacted=True,
        category="SCREENSHOT",
        original_name="ipoe.png",
        storage_path="runs/run-1/ipoe.png",
        media_type="image/png",
        file_size=10,
        sha256="a" * 64,
    )
    db_session.add(evidence)
    db_session.commit()
    assert evidence.step_ref == "IPOE_ADDRESS"


def test_result_derived_snapshots_can_be_sealed_once(result):
    seal_result_derived_snapshots(
        result,
        observations={"ipoe.ip": "192.0.2.10"},
        matched_rule_codes=["IPOE_HAS_IP"],
        standard_evaluations=[{"code": "IPOE_HAS_IP", "verdict": "PASS"}],
        evidence_validation={"complete": True},
    )
    with pytest.raises(ValueError, match="already sealed"):
        seal_result_derived_snapshots(
            result,
            observations={},
            matched_rule_codes=[],
            standard_evaluations=[],
            evidence_validation={"complete": False},
        )
```

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_skill_evidence_metadata_migration.py backend\tests\test_execution_session_models.py backend\tests\test_test_execution_service.py -q --basetemp data\pytest-skill-metadata-red
```

Expected: imports/columns/helper assertions fail because `0021` and the sealing helper do not exist.

- [ ] **Step 3: Implement additive columns and one-time sealing**

Use non-null server defaults only where legacy rows require them:

```python
def seal_result_derived_snapshots(
    result: RunResult,
    *,
    observations: dict[str, Any],
    matched_rule_codes: list[str],
    standard_evaluations: list[dict[str, Any]],
    evidence_validation: dict[str, Any],
) -> None:
    fields = {
        "observations": observations,
        "matched_rule_codes": matched_rule_codes,
        "standard_evaluations": standard_evaluations,
        "evidence_validation": evidence_validation,
    }
    if any(getattr(result, name) is not None for name in fields):
        raise ValueError("Result derived snapshots are already sealed")
    for name, value in fields.items():
        setattr(result, name, value)
```

Keep these fields immutable after the first non-null assignment and always immutable after `integrity_status='LOCKED'`.

- [ ] **Step 4: Implement and test migration `0021`**

The migration must upgrade a populated `0020` database, preserve every V1/V2 row, create indexes on `evidences.execution_session_id` and `(execution_session_id, step_ref)`, and downgrade only when no evidence uses the new session/step metadata and no interaction has a response payload.

- [ ] **Step 5: Run focused and full migration tests**

Run:

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_skill_evidence_metadata_migration.py backend\tests\test_execution_session_models.py backend\tests\test_test_execution_service.py -q --basetemp data\pytest-skill-metadata
.\.venv\Scripts\python -m pytest backend\tests -q -k "migration" --basetemp data\pytest-skill-migrations
```

Expected: zero failures.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/models backend/migrations/versions/20260918_0021_skill_evidence_metadata.py backend/tests
git commit -m "feat(skill): add execution evidence metadata"
```

---

### Task 2: Define and install the DRAFT Skill catalog

**Files:**
- Create: `backend/app/skill_catalog/__init__.py`
- Create: `backend/app/skill_catalog/definitions.py`
- Create: `backend/app/skill_catalog/onu_registration_dual_wan.py`
- Create: `backend/app/skill_catalog/repository.py`
- Create: `backend/app/skill_catalog/service.py`
- Create: `backend/app/skill_catalog/schemas.py`
- Create: `backend/app/skill_catalog/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_skill_catalog.py`
- Create: `backend/tests/test_skill_catalog_api.py`

**Interfaces:**
- Produces frozen `CatalogDefinition`, `ActionDefinition`, `EvidenceDefinition`, and `RequirementDefinition` DTOs.
- Produces `SkillCatalogService.install_onu_registration_dual_wan_draft() -> CatalogInstallResult`.
- Produces `GET /api/skills`, `GET /api/skills/{skill_id}`, and `POST /api/skills/catalog/onu-registration-dual-wan/install-draft`.

- [ ] **Step 1: Write failing idempotency and content tests**

```python
def test_catalog_install_is_idempotent(db_session):
    service = build_catalog_service(db_session)
    first = service.install_onu_registration_dual_wan_draft()
    second = service.install_onu_registration_dual_wan_draft()
    assert first.skill_id == second.skill_id
    assert second.created is False
    assert second.evidence_codes == (
        "E1_OLT_AUTOFIND", "E2_REGISTRATION", "E3_IPOE_ADDRESS",
        "E4_IPOE_PING", "E5_PPPOE_ADDRESS", "E6_PPPOE_PING",
    )
```

Assert the definition contains both WAN modes, both dual-WAN policies, RESTORE/KEEP, six evidence groups, MA5800-X7 applicability, and no secret default values.

- [ ] **Step 2: Run the tests and confirm RED**

Run:

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_skill_catalog.py backend\tests\test_skill_catalog_api.py -q --basetemp data\pytest-skill-catalog-red
```

Expected: `app.skill_catalog` cannot be imported.

- [ ] **Step 3: Implement immutable catalog DTOs and exact DRAFT definition**

```python
@dataclass(frozen=True)
class CatalogDefinition:
    skill_code: str
    version: str
    standard_code: str
    standard_version: str
    test_case_code: str
    parameters: tuple[ParameterDefinition, ...]
    steps: tuple[StepDefinition, ...]
    requirements: tuple[RequirementDefinition, ...]
    evidence: tuple[EvidenceDefinition, ...]
    actions: tuple[ActionDefinition, ...]
```

The exact definition must be data-only. It may contain stable action codes and human instructions, but no OLT command strings, selectors, passwords, hosts, SNs, or PPPoE users.

- [ ] **Step 4: Implement transactional, idempotent installation**

Create or reuse the V1 Test Case, DRAFT Test Standard/Profile, DRAFT Test Skill, child rows, DEVELOPMENT Runner Plugins/Actions, SkillCase, and SkillRunnerBindings in one transaction. If a matching catalog version already exists with a different definition hash, return `409 Catalog version conflict`; never overwrite it.

- [ ] **Step 5: Implement read-only API and tests**

Return Skill metadata, parameters, steps, evidence rules, publication status, supported OLT, and definition hash. Do not expose Runner command construction or credential handles.

- [ ] **Step 6: Run tests and commit**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_skill_catalog.py backend\tests\test_skill_catalog_api.py -q --basetemp data\pytest-skill-catalog
git add backend/app/skill_catalog backend/app/main.py backend/tests/test_skill_catalog.py backend/tests/test_skill_catalog_api.py
git commit -m "feat(skill): add dual WAN draft catalog"
```

---

### Task 3: Add secure local Runner contracts, credentials, and artifact writer

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py`
- Create: `backend/app/local_runner/__init__.py`
- Create: `backend/app/local_runner/contracts.py`
- Create: `backend/app/local_runner/registry.py`
- Create: `backend/app/local_runner/credentials.py`
- Create: `backend/app/local_runner/credential_router.py`
- Modify: `backend/app/main.py`
- Create: `backend/app/local_runner/evidence.py`
- Create: `backend/tests/test_local_runner_registry.py`
- Create: `backend/tests/test_local_runner_credentials.py`
- Create: `backend/tests/test_local_credential_api.py`
- Create: `backend/tests/test_local_runner_evidence.py`

**Interfaces:**
- Produces `ActionContext`, `Observation`, `ArtifactPayload`, `ActionOutcome`, and `ActionHandler`.
- Produces `LocalActionRegistry.register(plugin_code, action_code, handler)` and `.resolve(...)` with exact allow-list matching.
- Produces `CredentialResolver.resolve(reference: str) -> SecretValue` backed by `keyring`, plus a fake for tests.
- Produces local-only `PUT /api/local-credentials/{reference}`, `GET /api/local-credentials/{reference}/status`, and `DELETE /api/local-credentials/{reference}`; no response contains a secret.
- Produces `GeneratedEvidenceWriter.write_text_and_png(...)` and `.register_screenshot(...)`.

- [ ] **Step 1: Add dependencies and write security-first failing tests**

Add:

```toml
"keyring>=25,<26",
"paramiko>=3.5,<4",
"pillow>=11,<12",
```

Test that unknown action codes are rejected, absolute/traversal evidence paths are rejected, secret patterns are redacted before disk write, and `SecretValue` has a redacted `repr`. API tests must prove credential enrollment writes only to the injected keyring provider, database tables remain unchanged, request bodies are not logged, and responses contain only `{reference, available}`.

- [ ] **Step 2: Run tests and confirm RED**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_local_runner_registry.py backend\tests\test_local_runner_credentials.py backend\tests\test_local_credential_api.py backend\tests\test_local_runner_evidence.py -q --basetemp data\pytest-local-runner-red
```

- [ ] **Step 3: Implement minimal frozen contracts and registry**

```python
@dataclass(frozen=True)
class ActionOutcome:
    status: Literal["PASS", "FAIL", "BLOCKED", "ERROR", "WAITING_OPERATOR"]
    observations: tuple[Observation, ...]
    artifacts: tuple[ArtifactPayload, ...]
    error_code: str | None = None
    detail: str | None = None


class ActionHandler(Protocol):
    def execute(self, context: ActionContext) -> ActionOutcome: ...
```

`ActionContext.parameters` contains validated non-secret values; resolved secrets are separate `SecretValue` instances and may not enter event payloads.

- [ ] **Step 4: Implement keyring resolver and local credential API**

Use service name `ONU Test Workbench`; validate references against `^[A-Za-z0-9._:-]{1,200}$`. Bind credential routes only to the existing loopback API and add `Cache-Control: no-store`. Accept a secret only in the PUT request body, pass it directly to keyring, clear application references after the call, never echo it, and never include request bodies in logs.

- [ ] **Step 5: Implement evidence writer**

Render terminal PNG at 1920px maximum width, include action title and capture timestamp, and hash both TXT and PNG after redaction.

- [ ] **Step 6: Run tests and commit**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_local_runner_registry.py backend\tests\test_local_runner_credentials.py backend\tests\test_local_credential_api.py backend\tests\test_local_runner_evidence.py -q --basetemp data\pytest-local-runner
git add backend/pyproject.toml backend/app/core/config.py backend/app/local_runner backend/app/main.py backend/tests/test_local_runner_*.py backend/tests/test_local_credential_api.py
git commit -m "feat(runner): add secure local action foundation"
```

---

### Task 4: Implement the MA5800-X7 parser and transport

**Files:**
- Create: `backend/app/local_runner/ma5800/__init__.py`
- Create: `backend/app/local_runner/ma5800/parsers.py`
- Create: `backend/app/local_runner/ma5800/transport.py`
- Create: `backend/tests/fixtures/ma5800/autofind.txt`
- Create: `backend/tests/fixtures/ma5800/ont_online.txt`
- Create: `backend/tests/fixtures/ma5800/wan_ipoe.txt`
- Create: `backend/tests/fixtures/ma5800/wan_pppoe.txt`
- Create: `backend/tests/fixtures/ma5800/command_failure.txt`
- Create: `backend/tests/test_ma5800_parsers.py`
- Create: `backend/tests/test_ma5800_transport.py`

**Interfaces:**
- Produces `AutofindObservation`, `OntStateObservation`, `WanObservation`, `ServicePortObservation`.
- Produces pure `parse_autofind`, `parse_ont_state`, `parse_wan_info`, and `parse_command_result`.
- Produces `MA5800Transport.run(command: SafeMA5800Command) -> CommandTranscript`.

- [ ] **Step 1: Copy only redacted, representative fixture text from existing lab evidence**

Fixtures must remove Password/LOID/PPPoE material while preserving prompts, paging markers, `<cr>` confirmation, ANSI cursor sequences, success fields, and failure lines.

- [ ] **Step 2: Write failing parser tests**

```python
def test_parse_autofind_extracts_target():
    result = parse_autofind(load_fixture("autofind.txt"))
    assert result[0].fsp == "0/2/10"
    assert result[0].serial_number == "48575443DD91BBBB"


def test_transport_handles_more_and_cr_prompts(fake_channel):
    fake_channel.queue("---- More ----", "{ <cr>|desc<K> }:", "MA5800-X7#")
    transcript = build_transport(fake_channel).run(SafeMA5800Command("display_autofind", ()))
    assert fake_channel.sent == ["display ont autofind all\n", " ", "\n"]
    assert transcript.prompt == "MA5800-X7#"
```

- [ ] **Step 3: Implement pure normalization and parsers**

Normalize ANSI cursor movement before parsing, preserve redacted raw output, distinguish `NO_AUTOFIND_RESULT` from command failure, and never infer PASS only from absence of the word `Failure`.

- [ ] **Step 4: Implement Paramiko transport with host-key policy**

Default to a pinned host-key fingerprint from the environment template. A missing fingerprint requires an operator interaction before first trust; never use unconditional `AutoAddPolicy` in FORMAL mode.

- [ ] **Step 5: Run tests and commit**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_ma5800_parsers.py backend\tests\test_ma5800_transport.py -q --basetemp data\pytest-ma5800-core
git add backend/app/local_runner/ma5800 backend/tests/fixtures/ma5800 backend/tests/test_ma5800_*.py
git commit -m "feat(runner): parse and transport MA5800 sessions"
```

---

### Task 5: Implement allow-listed MA5800 actions and guarded mutation previews

**Files:**
- Create: `backend/app/local_runner/ma5800/actions.py`
- Create: `backend/tests/test_ma5800_actions.py`
- Modify: `backend/app/local_runner/registry.py`
- Modify: `backend/app/skill_catalog/onu_registration_dual_wan.py`

**Interfaces:**
- Produces handlers for `ma5800.preflight`, `discover_onts`, `snapshot_ont`, `find_free_ont_id`, `delete_ont`, `register_ont`, `provision_ipoe`, `provision_pppoe`, `read_wan_info`, `remove_test_services`, `restore_snapshot`, and `verify_restore`.
- Produces `MutationPreview(action_code, target_fsp, ont_id, serial_number, affected_service_ports, summary)` before every mutation.

- [ ] **Step 1: Write failing command-construction and safety tests**

```python
def test_register_action_builds_command_only_from_validated_fields():
    command = build_register_command(valid_registration_parameters())
    assert command.text == (
        "ont add 10 36 sn-auth 48575443DD91BBBB omci "
        "ont-lineprofile-id 10 ont-srvprofile-id 10"
    )


@pytest.mark.parametrize("value", ["10;quit", "../10", "10\nundo service-port 1"])
def test_numeric_fields_reject_command_injection(value):
    with pytest.raises(ParameterValidationError):
        validate_gpon_port(value)
```

Also prove delete/restore handlers return `WAITING_OPERATOR` until the matching interaction response contains the preview hash and `approved=true`.

- [ ] **Step 2: Run tests and confirm RED**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_ma5800_actions.py -q --basetemp data\pytest-ma5800-actions-red
```

- [ ] **Step 3: Implement typed command builders**

Every command builder accepts validated integers, enum values, normalized SN, and `SecretValue` only. Command text is constructed inside the action module and never serialized into a database event. Event payloads contain action code, target identifiers, transcript hash, parsed observations, and redacted artifact IDs.

- [ ] **Step 4: Implement snapshot/restore semantics**

Snapshot must capture registration, line/service profiles, IP host/WAN state, and service-port identifiers before mutation. Restore applies only data present in the immutable snapshot, then `verify_restore` re-queries and compares normalized state. An unsupported or unverified restore path returns `RECOVERY_REQUIRED` with explicit manual instructions.

- [ ] **Step 5: Register actions and run tests**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_ma5800_actions.py backend\tests\test_local_runner_registry.py -q --basetemp data\pytest-ma5800-actions
git add backend/app/local_runner/ma5800/actions.py backend/app/local_runner/registry.py backend/app/skill_catalog/onu_registration_dual_wan.py backend/tests/test_ma5800_actions.py
git commit -m "feat(runner): add guarded MA5800 actions"
```

---

### Task 6: Capture ONU Web WAN and Ping evidence

**Files:**
- Create: `backend/app/local_runner/onu_web/__init__.py`
- Create: `backend/app/local_runner/onu_web/contracts.py`
- Create: `backend/app/local_runner/onu_web/selectors.py`
- Create: `backend/app/local_runner/onu_web/neutral.py`
- Modify: `backend/app/diagnostics/adapters/huawei.py`
- Create: `backend/tests/test_onu_web_adapter.py`
- Modify: `backend/tests/test_diagnostic_adapters.py`

**Interfaces:**
- Produces `ONUWebAdapter.capture_wan(context, wan_mode) -> ActionOutcome`.
- Produces `ONUWebAdapter.run_ping(context, wan_mode, target, packet_count) -> ActionOutcome`.
- Produces `ONUWebAdapterRegistry.resolve(adapter_key: str)`, starting with the code-owned `neutral-v1` profile and rejecting unknown firmware families.
- Reuses `HuaweiSelectorStrategy` and Ping parsing without duplicating selector or packet logic.

- [ ] **Step 1: Write failing tests using fake Playwright surfaces**

Assert the adapter selects the requested WAN, extracts IP/mask/gateway/DNS/VLAN/status, captures full-page PNG plus page text, and returns BLOCKED with selector diagnostics when the product page cannot be interpreted.

```python
def test_capture_wan_returns_address_and_two_artifacts(fake_surface):
    outcome = build_adapter(fake_surface).capture_wan(context("IPOE"), "IPOE")
    assert observation(outcome, "ipoe.ip_address") == "192.0.2.10"
    assert {item.media_type for item in outcome.artifacts} == {"image/png", "text/plain"}
```

- [ ] **Step 2: Run tests and confirm RED**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_onu_web_adapter.py backend\tests\test_diagnostic_adapters.py -q --basetemp data\pytest-onu-web-red
```

- [ ] **Step 3: Extract reusable selector/Ping functions and implement screenshots**

Keep selectors in code-owned firmware profiles, not in Skill JSON or user input. Use a 1920x1080 context, capture full-page PNG after the relevant WAN is visibly selected, save page text, and mask username/password inputs before screenshot. The Device/environment snapshot selects an allow-listed `onu_web_adapter_key`; an unknown key is BLOCKED rather than guessed.

- [ ] **Step 4: Implement precise failure mapping**

- Authentication rejected: BLOCKED `ONU_WEB_CREDENTIAL_REJECTED`.
- Page unavailable: BLOCKED `ONU_WEB_UNREACHABLE`.
- Expected WAN missing after successful provisioning: FAIL `WAN_NOT_VISIBLE`.
- Ping completed outside thresholds: FAIL with parsed sent/received/loss/latency observations.

- [ ] **Step 5: Run tests and commit**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_onu_web_adapter.py backend\tests\test_diagnostic_adapters.py -q --basetemp data\pytest-onu-web
git add backend/app/local_runner/onu_web backend/app/diagnostics/adapters/huawei.py backend/tests/test_onu_web_adapter.py backend/tests/test_diagnostic_adapters.py
git commit -m "feat(runner): capture ONU WAN and Ping evidence"
```

---

### Task 7: Add PC-side connectivity evidence without changing global routing

**Files:**
- Create: `backend/app/local_runner/pc_probe.py`
- Create: `backend/tests/test_pc_probe.py`
- Modify: `backend/app/skill_catalog/onu_registration_dual_wan.py`

**Interfaces:**
- Produces `PCProbe.run(ProbeRequest) -> ProbeObservation`.
- `ProbeRequest` contains `interface_name`, `source_address`, `ping_target`, `dns_name`, `https_url`, counts, and timeouts.
- Never changes Windows route metrics, adapter state, DNS configuration, or firewall rules.

- [ ] **Step 1: Write failing parser and command-boundary tests**

Test Windows English/Chinese Ping output, DNS success/failure, HTTPS status, interface/source validation, and subprocess argument lists with `shell=False`.

```python
def test_probe_uses_argument_list_and_never_shell(fake_subprocess):
    build_probe(fake_subprocess).run(valid_request())
    assert fake_subprocess.calls[0].shell is False
    assert fake_subprocess.calls[0].args[:2] == ["ping.exe", "-n"]
```

- [ ] **Step 2: Run tests and confirm RED**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_pc_probe.py -q --basetemp data\pytest-pc-probe-red
```

- [ ] **Step 3: Implement controlled probes and evidence rendering**

Ping is mandatory for E4/E6. DNS and HTTPS are optional Standard Profile checks. Render the redacted console transcript to PNG; if the computer cannot bind to the requested ONU-side interface, return `WAITING_OPERATOR` with instructions to connect LAN/Wi-Fi and retry.

- [ ] **Step 4: Run tests and commit**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_pc_probe.py -q --basetemp data\pytest-pc-probe
git add backend/app/local_runner/pc_probe.py backend/app/skill_catalog/onu_registration_dual_wan.py backend/tests/test_pc_probe.py
git commit -m "feat(runner): add PC connectivity evidence"
```

---

### Task 8: Persist and evaluate a resumable Skill execution

**Files:**
- Create: `backend/app/skill_execution/__init__.py`
- Create: `backend/app/skill_execution/repository.py`
- Create: `backend/app/skill_execution/evaluator.py`
- Create: `backend/app/skill_execution/coordinator.py`
- Create: `backend/app/skill_execution/service.py`
- Create: `backend/tests/test_skill_execution_repository.py`
- Create: `backend/tests/test_skill_evaluator.py`
- Create: `backend/tests/test_skill_coordinator.py`

**Interfaces:**
- Produces `CreateSkillExecutionCommand` and `SkillExecutionService.create_execution(command)`.
- Produces `SkillExecutionService.advance(session_id)`, `.respond(session_id, interaction_id, response)`, and `.get_view(session_id)`.
- `advance` executes at most one Runner action or creates one operator interaction, making every step resumable and testable.

- [ ] **Step 1: Write failing execution-creation tests**

Assert one transaction creates a LOCAL_RUNNER TestRun, RunResult with immutable Skill/parameter/standard snapshots, ExecutionSession, and initial event. Reject non-DRAFT catalog conflicts, missing environment parameters, plaintext-looking credential values, and unsupported OLT vendors.

- [ ] **Step 2: Write failing sequential/concurrent workflow tests**

```python
def test_sequential_mode_runs_ipoe_before_pppoe(coordinator):
    refs = drain_with_fake_passes(coordinator, mode="SEQUENTIAL_ISOLATED")
    assert refs.index("provision_ipoe") < refs.index("remove_ipoe")
    assert refs.index("remove_ipoe") < refs.index("provision_pppoe")


def test_concurrent_strict_mode_waits_for_each_wan_switch(coordinator):
    view = drain_until_waiting(coordinator, mode="CONCURRENT_DUAL_WAN", policy="STRICT_PER_WAN")
    assert view.pending_interaction.interaction_type == "SWITCH_ACTIVE_WAN"
    assert view.pending_interaction.options == ["IPOE_ACTIVE", "UNABLE", "CANCEL"]
```

- [ ] **Step 3: Implement repository creation and append-only event operations**

Use unique idempotency keys `<session>:<step>:<attempt>`. Never update or delete ExecutionEvent. Register generated Evidence through the existing storage boundary and link every artifact to result, session, step, and evidence rule.

- [ ] **Step 4: Implement coordinator branches and recovery**

The coordinator derives the next action only from immutable plan snapshots plus persisted events/interactions. On process restart, active sessions without a live runner become `RECOVERY_REQUIRED`; the next advance performs snapshot-aware restore or emits a manual Recovery Task.

- [ ] **Step 5: Implement evaluator**

```python
@dataclass(frozen=True)
class EvaluationResult:
    functional_verdict: Literal["PASS", "FAIL", "BLOCKED"]
    evidence_complete: bool
    overall_result: Literal["PASS", "FAIL", "BLOCKED"]
    matched_rule_codes: tuple[str, ...]
    evaluations: tuple[dict[str, JsonValue], ...]
```

Evaluate BLOCKED before FAIL only for missing prerequisites/environment; a completed device observation outside a mandatory threshold is FAIL. PASS requires E1–E6 complete. Seal result-derived snapshots once, update the draft result, then lock through `TestExecutionService.lock_result`.

- [ ] **Step 6: Run tests and commit**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_skill_execution_repository.py backend\tests\test_skill_evaluator.py backend\tests\test_skill_coordinator.py -q --basetemp data\pytest-skill-execution
git add backend/app/skill_execution backend/tests/test_skill_execution_*.py backend/tests/test_skill_evaluator.py
git commit -m "feat(skill): orchestrate resumable dual WAN execution"
```

---

### Task 9: Expose the Skill execution API

**Files:**
- Create: `backend/app/skill_execution/schemas.py`
- Create: `backend/app/skill_execution/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_skill_execution_api.py`

**Interfaces:**
- `POST /api/skill-executions`
- `GET /api/skill-executions/{session_id}`
- `POST /api/skill-executions/{session_id}/advance`
- `POST /api/skill-executions/{session_id}/interactions/{interaction_id}/respond`
- `GET /api/skill-executions/{session_id}/evidence`

- [ ] **Step 1: Write failing API contract tests**

```python
def test_create_execution_returns_snapshotted_session(client, seeded_catalog):
    response = client.post("/api/skill-executions", json=valid_execution_request())
    assert response.status_code == 201
    body = response.json()
    assert body["skill_code"] == "ONU_REGISTRATION_DUAL_WAN_CONNECTIVITY"
    assert body["wan_mode"] == "SEQUENTIAL_ISOLATED"
    assert body["status"] == "CREATED"
```

Test 409 for active-session conflict, 422 for unsupported modes/OLT/secret-shaped values, 404 for unknown session, and 409 for stale interaction response or mismatched preview hash.

- [ ] **Step 2: Run tests and confirm RED**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_skill_execution_api.py -q --basetemp data\pytest-skill-api-red
```

- [ ] **Step 3: Implement Pydantic schemas and dependency factories**

API responses expose observations, verdicts, evidence metadata, event summaries, and human instructions. They never expose credentials, command text, local absolute storage paths, or raw unredacted OLT output.

- [ ] **Step 4: Implement exception mapping and startup recovery scan**

Map validation to 422, not found to 404, active/stale conflicts to 409, and evidence integrity failures to 410/409 consistent with existing APIs. Startup scans active sessions and marks only interrupted RUNNING/RESTORING sessions as RECOVERY_REQUIRED; WAITING_OPERATOR remains resumable.

- [ ] **Step 5: Run API and full backend tests, then commit**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_skill_execution_api.py -q --basetemp data\pytest-skill-api
.\.venv\Scripts\python -m pytest backend\tests -q --basetemp data\pytest-skill-backend
git add backend/app/main.py backend/app/skill_execution/schemas.py backend/app/skill_execution/router.py backend/tests/test_skill_execution_api.py
git commit -m "feat(skill): expose dual WAN execution API"
```

---

### Task 10: Build the first-Skill execution wizard and evidence view

**Files:**
- Create: `frontend/src/skillExecution/types.ts`
- Create: `frontend/src/skillExecution/api.ts`
- Create: `frontend/src/skillExecution/api.test.ts`
- Create: `frontend/src/skillExecution/SkillConfigurationForm.tsx`
- Create: `frontend/src/skillExecution/OperatorInteractionDialog.tsx`
- Create: `frontend/src/skillExecution/EvidenceGrid.tsx`
- Create: `frontend/src/skillExecution/SkillExecutionPage.tsx`
- Create: `frontend/src/skillExecution/SkillExecutionPage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Produces `SkillExecutionApi` matching Task 9.
- Adds the “测试能力” module and renders `SkillExecutionPage`.
- Polling is not required: the page calls `advance` explicitly after each completed action and stops at WAITING_OPERATOR or a terminal status.

- [ ] **Step 1: Write failing API and page tests**

Cover Skill loading, required parameter validation, credential availability/enrollment without secret echo, mode/policy behavior, create/advance, risk dialog content, stale response conflict, E1–E6 cards, FAIL/BLOCKED wording, restore/keep choice, and no secret rendering.

```tsx
it("shows the six required evidence groups", async () => {
  render(<SkillExecutionPage api={fakeApiWithCompletedExecution()} />);
  for (const code of ["E1", "E2", "E3", "E4", "E5", "E6"]) {
    expect(await screen.findByTestId(`evidence-${code}`)).toBeInTheDocument();
  }
});
```

- [ ] **Step 2: Run tests and confirm RED**

```powershell
Set-Location frontend
npm.cmd test -- src/skillExecution/SkillExecutionPage.test.tsx src/skillExecution/api.test.ts --reporter=dot --maxWorkers=1
Set-Location ..
```

- [ ] **Step 3: Implement configuration and progress UI**

The form shows resolved values from Device/Environment/Standard sources, marks overrides, and sends credential references only. Concurrent mode reveals strict/customer-simplified policy; customer-simplified is disabled unless allowed by the selected Standard Profile.

- [ ] **Step 4: Implement interaction dialog and evidence grid**

For HIGH risk interactions require a checked confirmation plus exact target summary; KEEP configuration must explicitly state that the lab is left changed. Evidence cards display source, capture time, SHA256 status, standard clause, and thumbnail/download action.

- [ ] **Step 5: Run frontend tests/build and commit**

```powershell
Set-Location frontend
npm.cmd test -- --reporter=dot --maxWorkers=1
npm.cmd run build
Set-Location ..
git add frontend/src
git commit -m "feat(skill): add dual WAN execution wizard"
```

---

### Task 11: Add offline double-click startup and generated report coverage

**Files:**
- Create: `scripts/install-local.ps1`
- Create: `scripts/build-offline-bundle.ps1`
- Create: `scripts/start-workbench.ps1`
- Create: `Start ONU Test Workbench.cmd`
- Create: `vendor/OFFLINE_BUNDLE_MANIFEST.json`
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/config.py`
- Create: `backend/tests/test_static_frontend.py`
- Modify: `backend/app/reports/snapshots.py`
- Modify: `backend/app/reports/renderer.py`
- Modify: `backend/tests/test_report_snapshot.py`
- Modify: `backend/tests/test_report_service.py`
- Create: `backend/tests/test_skill_report.py`
- Create: `docs/ONU_REGISTRATION_DUAL_WAN_SKILL.md`

**Interfaces:**
- Bundle builder produces Python wheels, a Playwright Chromium bundle, frontend static assets, and SHA256 manifest while a packaging machine is online.
- Installer consumes only the checksummed offline bundle; it does not invoke npm or contact a package registry.
- Launcher migrates the configured database to head, starts the backend that serves `/api` plus built frontend assets, waits for `/api/health`, then opens the local browser.
- Reports render Skill/Standard snapshots, verdicts, E1–E6, operator confirmations, recovery, and hashes.

- [ ] **Step 1: Write failing report tests**

Assert the HTML contains Skill/version, mode/policy, registration/IPoE/PPPoE verdicts, six evidence headings, thumbnails, standard clauses, redaction labels, operator decisions, recovery status, and no secret fixture markers.

- [ ] **Step 2: Implement report snapshot and renderer changes**

Never read current mutable Skill/Standard rows while rendering historical reports; render only the Run/Result snapshots and linked immutable Evidence metadata.

- [ ] **Step 3: Implement the reproducible offline bundle builder**

`build-offline-bundle.ps1` runs `pip wheel ./backend --wheel-dir vendor/wheels`, installs frontend dependencies on the packaging machine, runs the production build, copies `frontend/dist` to `vendor/frontend`, downloads the matching Playwright Chromium into `vendor/playwright`, and writes SHA256 plus size for every bundled file to `vendor/OFFLINE_BUNDLE_MANIFEST.json`. It fails if the working tree contains a tracked credential-like file or if frontend/backend validation fails.

- [ ] **Step 4: Serve the built frontend and implement installer/launcher exit checks**

Mount the configured `vendor/frontend` directory through FastAPI `StaticFiles` only after all `/api` routers, with SPA fallback to `index.html`; `test_static_frontend.py` proves API routing is not shadowed and unknown UI routes return the SPA shell. `install-local.ps1` verifies every manifest hash, verifies Python version, creates `.venv`, installs runtime wheels with `--no-index --find-links vendor/wheels`, installs the bundled Playwright browser path, migrates the database, and creates a desktop shortcut. It does not require Node on the target computer. It stops with a Chinese error dialog when an artifact is missing. `start-workbench.ps1` refuses to start on a failed migration or occupied port, launches only Uvicorn, waits for health, opens the local URL, and writes local logs.

- [ ] **Step 5: Test from a disconnected Windows account**

Disable external network access while leaving the lab ONU/OLT LAN connected. Run the installer, double-click the launcher, verify the health endpoint and UI, and record exact dependency artifacts needed in `docs/ONU_REGISTRATION_DUAL_WAN_SKILL.md`.

- [ ] **Step 6: Run report/backend/frontend checks and commit**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_skill_report.py backend\tests\test_report_snapshot.py backend\tests\test_report_service.py backend\tests\test_static_frontend.py -q --basetemp data\pytest-skill-report
Set-Location frontend
npm.cmd test -- --reporter=dot --maxWorkers=1
npm.cmd run build
Set-Location ..
git add scripts "Start ONU Test Workbench.cmd" vendor/OFFLINE_BUNDLE_MANIFEST.json backend/app/main.py backend/app/core/config.py backend/app/reports backend/tests docs/ONU_REGISTRATION_DUAL_WAN_SKILL.md
git commit -m "feat(skill): package offline dual WAN workflow"
```

---

### Task 12: Execute the real MA5800-X7 validation gate

**Files:**
- Create: `docs/ONU_REGISTRATION_DUAL_WAN_LAB_RUNBOOK.md`
- Create: `docs/ONU_REGISTRATION_DUAL_WAN_VALIDATION_RECORD.md`
- Modify only when observed evidence proves a mismatch: MA5800 parser/action, ONU Web adapter, catalog thresholds, coordinator, or tests.

**Interfaces:**
- Consumes the complete DRAFT Skill and the user's connected MA5800-X7/ONU environment.
- Produces one PASS, one controlled FAIL, one BLOCKED/recovery record, and the evidence needed for an explicit publication decision.

- [ ] **Step 1: Write the exact safety runbook before connecting**

Record the selected OLT host reference, F/S/P, ONU SN, free ONT ID policy, profile IDs, VLAN, credential references, Ping targets, initial configuration snapshot, rollback owner, and emergency stop procedure. Do not put secret values in the runbook.

- [ ] **Step 2: Run read-only actions and inspect E1 rendering**

Execute preflight, autofind, current registration, WAN, and service-port queries. Compare parsed fields with the OLT screen. If any mismatch exists, add the redacted transcript as a test fixture, write a failing parser test, fix it, and rerun before permitting mutation.

- [ ] **Step 3: Run the guarded registration scenario**

Use an unregistered ONU for the first mutation run. Confirm the displayed target and snapshot before registration. Verify O5/online/match and E2. Then validate existing-registration detection and the delete confirmation with a controlled test record.

- [ ] **Step 4: Run sequential isolated WAN PASS**

Verify IPoE E3/E4, remove/disable IPoE with confirmation, then verify PPPoE E5/E6. Confirm the PC and ONU Ping traffic uses the intended active WAN. Validate RESTORE and compare normalized pre/post snapshots.

- [ ] **Step 5: Run concurrent dual-WAN PASS**

Provision both WANs with distinct host indexes. Validate strict per-WAN switching and, in a separate DEVELOPMENT execution, customer-simplified reporting wording. Do not publish simplified policy unless a customer Standard Profile explicitly allows it.

- [ ] **Step 6: Produce controlled FAIL and BLOCKED records**

Create an injected-fault DEVELOPMENT execution by applying a deliberately impossible Ping threshold to a known successful observation; label it `VALIDATION_INJECTED_FAULT` and exclude it from product-quality statistics. This proves the real evidence/evaluator/report FAIL path without claiming the DUT is defective. Create BLOCKED by cancelling an operator interaction or withholding a required lab connection. Verify recovery tasks and final restoration.

- [ ] **Step 7: Calibrate and rerun all automated gates**

Any command, prompt, page, timeout, parser, screenshot, or threshold correction follows red-green TDD and receives a task-scoped commit. Then run:

```powershell
.\.venv\Scripts\python -m alembic -c backend\alembic.ini heads
.\.venv\Scripts\python -m pytest backend\tests -q --basetemp data\pytest-dual-wan-final
Set-Location frontend
npm.cmd test -- --reporter=dot --maxWorkers=1
npm.cmd run build
Set-Location ..
git diff --check
```

Expected: one Alembic head, zero test failures, successful frontend build, and clean diff check.

- [ ] **Step 8: Record publication decision**

`docs/ONU_REGISTRATION_DUAL_WAN_VALIDATION_RECORD.md` must link the PASS/FAIL/BLOCKED run numbers, E1–E6 hashes, restore result, known product/firmware coverage, and remaining limitations. Keep catalog rows DRAFT/DEVELOPMENT unless the user explicitly approves publication after reviewing this record.

- [ ] **Step 9: Commit the validation checkpoint**

```powershell
git add docs backend frontend
git commit -m "test(skill): validate ONU registration and dual WAN workflow"
```

## Final Release Gates

- Alembic has exactly one head after `0021`.
- V1→latest migration preserves the existing closed-loop fixture and all hashes.
- Full backend and frontend suites pass; production frontend build succeeds.
- Catalog installation is idempotent and conflicts rather than overwriting a changed version.
- Database schema contains no secret or arbitrary command payload columns.
- Source scan finds no committed lab credentials, PPPoE values, ONU passwords, OLT passwords, or raw unredacted evidence.
- E1–E6 are complete and hash-valid in the PASS validation run.
- FAIL and BLOCKED are correctly distinguished in recorded real runs.
- RESTORE is verified or a visible MANUAL_REQUIRED Recovery Task remains; no run silently claims restoration.
- The Skill remains DRAFT until the user approves the real validation record.
