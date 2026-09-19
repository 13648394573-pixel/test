# ONU 现场只读兼容性检查 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不修改 OLT/ONU 配置的前提下，为现场人员提供中文浏览器入口，验证 MA5800-X7、ONU Web、电脑网卡和本地证据链能否进入正式 ONU 注册与双 WAN Skill 验证。

**Architecture:** 新增独立 `lab_compatibility` 应用边界，用文件化报告保存运行状态，不创建 TestRun、Result 或 Defect。OLT 经过第二层只读白名单；ONU Web 只导航、读取和截图；PC Probe 只使用指定源地址执行 Ping。FastAPI 只在 loopback 下提供接口，React 页面展示四步向导。

**Tech Stack:** Python 3.12、FastAPI、Pydantic、Paramiko、Playwright、Pillow、React 19、TypeScript、Vitest、pytest。

**Spec:** `docs/superpowers/specs/2026-09-19-read-only-lab-compatibility-check-design.md`

## Global Constraints

- 本检查是 `ONU_REGISTRATION_DUAL_WAN_CONNECTIVITY` 的前置安全门禁，不是正式测试执行。
- 不创建 TestRun、Result、Defect、回归或报告归档记录，不新增数据库迁移。
- OLT 只允许会话导航和固定 `display` 查询；注册、删除、WAN 下发、service-port 修改、保存和重启均不可达。
- `config` 与 `interface gpon` 只用于进入查询所需 CLI 上下文，不能携带配置命令。
- ONU Web 不执行 ONU Ping，不保存 WAN，不点击配置提交按钮。
- PC Probe 不修改路由、metric、DNS、网卡状态或防火墙。
- API 只传凭据引用；秘密只从 Windows 凭据保险箱解析，不写入数据库、日志、API 或证据。
- 状态使用 `VERIFIED/NEEDS_INPUT/BLOCKED/NOT_RUN` 和 `READY/PARTIAL/BLOCKED`，不使用产品 PASS/FAIL。
- 设备地址必须经过本地或私有地址校验；不接受带用户名或密码的 URL。
- 离线安装和双击启动仍由主计划 Task 11 交付，本计划不创建第二套安装器。

## Review Focus

- 首次连接必须先显示 OLT 主机指纹并由工作人员确认；指纹变化必须阻塞。Task 1、4 覆盖。
- SN、F/S/P、ONT ID 只提供一部分时不得猜测命令，应返回 `NEEDS_INPUT`。Task 3、4 覆盖。
- ONU 未注册或没有 WAN 时不得判产品失败，应形成 `PARTIAL` 和人工说明。Task 2、3 覆盖。
- 重复点击不得并发连接同一现场设备，应返回 409 并保留首个检查。Task 3、4、5 覆盖。
- OLT 输出或 ONU 页面结构不支持时须保留脱敏证据并返回 `BLOCKED`。Task 1、2、3 覆盖。

---

### Task 1: 建立 MA5800-X7 只读连接与命令门禁

**Files:**
- Modify: `backend/app/local_runner/ma5800/transport.py`
- Create: `backend/app/lab_compatibility/__init__.py`
- Create: `backend/app/lab_compatibility/olt_probe.py`
- Modify: `backend/tests/test_ma5800_transport.py`
- Create: `backend/tests/test_lab_compatibility_olt.py`

**Interfaces:**
- Consumes: `SafeMA5800Command`, `MA5800Transport`, `MA5800SSHConnector` and existing parsers.
- Produces: `MA5800SSHConnector.preview_host_key(hostname, port, timeout_seconds=10) -> str`.
- Produces: `ReadOnlyMA5800Executor.run(command) -> CommandTranscript`.
- Produces: `MA5800ReadOnlyProbe.run(request, username, password) -> OLTProbeResult`.

- [ ] **Step 1: Write failing transport tests**

```python
def test_interface_context_accepts_only_numeric_frame_and_slot():
    command = SafeMA5800Command("enter_gpon_interface", (0, 2))
    assert command.render() == "interface gpon 0/2"


def test_synchronize_drains_banner_without_sending_input():
    channel = FakeChannel(["Welcome\r\nMA5800-X7>"])
    transport = MA5800Transport(channel, sleeper=lambda _n: None)
    assert transport.synchronize() == "MA5800-X7>"
    assert channel.sent == []


def test_preview_host_key_always_closes_transport(fake_paramiko_transport):
    assert connector.preview_host_key("192.168.87.204", 22).startswith("SHA256:")
    assert fake_paramiko_transport.closed is True
```

- [ ] **Step 2: Run focused transport tests and confirm RED**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_ma5800_transport.py -q --basetemp data\pytest-compat-transport-red
```

Expected: fail because `enter_gpon_interface`, `synchronize`, and `preview_host_key` do not exist.

- [ ] **Step 3: Implement safe session navigation and host-key preview**

```python
def _enter_gpon_interface(arguments: tuple[Any, ...]) -> str:
    if len(arguments) != 2:
        return _invalid_arguments("enter_gpon_interface")
    frame = _int_arg(arguments[0], maximum=15)
    slot = _int_arg(arguments[1], maximum=31)
    return f"interface gpon {frame}/{slot}"
```

Register the renderer in `_SAFE_COMMANDS`. `synchronize()` reads until `PROMPT` without sending input. `preview_host_key()` validates a private/link-local/loopback IP, starts a Paramiko transport, reads the remote key, returns `host_key_fingerprint`, and closes in `finally`.

- [ ] **Step 4: Write failing read-only boundary tests**

```python
@pytest.mark.parametrize("action_code", [
    "register_ont", "delete_ont", "provision_ipoe",
    "provision_pppoe", "remove_service_port",
])
def test_read_only_executor_rejects_mutation_before_delegate(action_code):
    delegate = RecordingExecutor()
    executor = ReadOnlyMA5800Executor(delegate)
    with pytest.raises(ReadOnlyCommandViolation):
        executor.run(SafeMA5800Command(action_code, ()))
    assert delegate.commands == []
```

Also test `raw_cli`, unsafe SN, nonnumeric frame/slot, public OLT IP, fingerprint mismatch, paging, `{ <cr>... }:` prompts, unsupported output, and exact query order.

- [ ] **Step 5: Implement the read-only executor and probe**

```python
READ_ONLY_ACTIONS = frozenset({
    "enable", "disable_paging", "enter_config", "enter_gpon_interface",
    "display_autofind", "display_ont_by_sn", "display_ont_port",
    "display_wan_info", "display_service_ports",
})


class ReadOnlyMA5800Executor:
    def run(self, command: SafeMA5800Command) -> CommandTranscript:
        if command.action_code not in READ_ONLY_ACTIONS:
            raise ReadOnlyCommandViolation(command.action_code)
        return self.delegate.run(command)
```

Define immutable `OLTProbeRequest` containing host, port, fingerprint, optional SN, and optional complete frame/slot/PON/ONT target. The probe synchronizes, enters enable, disables paging, runs autofind and optional SN query, then enters config/interface only for a complete target. It parses current state and closes client/channel in `finally`; missing registration/WAN is observational, not product failure.

```python
@dataclass(frozen=True)
class OLTProbeRequest:
    host: str
    port: int
    expected_fingerprint: str
    onu_serial_number: str | None
    frame: int | None
    slot: int | None
    pon_port: int | None
    ont_id: int | None


@dataclass(frozen=True)
class OLTProbeResult:
    observations: tuple[Observation, ...]
    transcripts: tuple[CommandTranscript, ...]
    current_registration_found: bool
    current_wan_found: bool
```

- [ ] **Step 6: Run tests and commit**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_ma5800_transport.py backend\tests\test_lab_compatibility_olt.py -q --basetemp data\pytest-compat-olt
git add backend/app/local_runner/ma5800/transport.py backend/app/lab_compatibility backend/tests/test_ma5800_transport.py backend/tests/test_lab_compatibility_olt.py
git commit -m "feat(lab): enforce read-only MA5800 compatibility probe"
```

---

### Task 2: 增加不执行 Ping 的 ONU Web 探测

**Files:**
- Modify: `backend/app/local_runner/onu_web/contracts.py`
- Modify: `backend/app/local_runner/onu_web/neutral.py`
- Modify: `backend/tests/test_onu_web_adapter.py`

**Interfaces:**
- Consumes: `ONUWebSurface`, `NeutralONUWebAdapter`, existing selector strategy.
- Produces: `ONUWebSurface.assert_ping_controls() -> None`.
- Produces: `ONUWebCompatibilityResult(wan_outcome, ping_page_outcome)` and `NeutralONUWebAdapter.check_compatibility(context) -> ONUWebCompatibilityResult`.

- [ ] **Step 1: Write failing no-click tests**

```python
def test_probe_checks_pages_without_running_ping():
    surface = FakeSurface()
    result = NeutralONUWebAdapter(lambda _context: surface).check_compatibility(context())
    assert result.wan_outcome.status == "PASS"
    assert result.ping_page_outcome.status == "PASS"
    assert surface.opened_pages == ["wan", "ping"]
    assert surface.ping_controls_checked is True
    assert surface.ping_runs == 0
```

Assert four artifacts: WAN PNG/text and Ping-page PNG/text. Cover absent WAN, rejected credentials, unreachable page, missing navigation/control selectors, sensitive text, remote URL, and credential-bearing URL. No configured WAN is compatible when navigation and capture work.

- [ ] **Step 2: Run adapter tests and confirm RED**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_onu_web_adapter.py -q --basetemp data\pytest-compat-onu-red
```

- [ ] **Step 3: Implement selector-only checking and captures**

```python
def assert_ping_controls(self) -> None:
    HuaweiSelectorStrategy.first_usable(
        self.surface, NEUTRAL_V1.ping_target, "PING_TARGET"
    )
    HuaweiSelectorStrategy.first_usable(
        self.surface, NEUTRAL_V1.ping_start, "PING_START"
    )
```

`check_compatibility()` authenticates once, captures WAN without selecting/editing it, opens Ping, checks controls, captures again, masks sensitive controls before each capture, and closes in `finally`. It returns separate outcomes so a supported WAN page remains `VERIFIED` when only the Ping selector is blocked. It never calls `run_ping`.

```python
@dataclass(frozen=True)
class ONUWebCompatibilityResult:
    wan_outcome: ActionOutcome
    ping_page_outcome: ActionOutcome
```

- [ ] **Step 4: Run tests and commit**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_onu_web_adapter.py -q --basetemp data\pytest-compat-onu
git add backend/app/local_runner/onu_web/contracts.py backend/app/local_runner/onu_web/neutral.py backend/tests/test_onu_web_adapter.py
git commit -m "feat(lab): inspect ONU Web without running diagnostics"
```

---

### Task 3: 编排阶段并生成文件化报告

**Files:**
- Create: `backend/app/lab_compatibility/contracts.py`
- Create: `backend/app/lab_compatibility/store.py`
- Create: `backend/app/lab_compatibility/service.py`
- Modify: `backend/app/local_runner/evidence.py`
- Create: `backend/tests/test_lab_compatibility_store.py`
- Create: `backend/tests/test_lab_compatibility_service.py`
- Modify: `backend/tests/test_local_runner_evidence.py`

**Interfaces:**
- Consumes: credential resolver, Task 1 OLT probe, Task 2 ONU probe, `PCProbe`, evidence writer.
- Produces: `LabCompatibilityService.create(command)`, `.execute(check_id)`, `.get(check_id)`, `.preview_host_key(host, port)`.
- Produces: `CompatibilityReportStore.create/save/get/list_evidence` with atomic JSON writes.

- [ ] **Step 1: Write failing contracts and store tests**

```python
StageStatus = Literal["VERIFIED", "NEEDS_INPUT", "BLOCKED", "NOT_RUN"]
OverallStatus = Literal["READY", "PARTIAL", "BLOCKED"]
Lifecycle = Literal["PENDING", "RUNNING", "COMPLETED"]


def test_store_rejects_non_uuid_check_id(tmp_path):
    with pytest.raises(InvalidCompatibilityCheckId):
        CompatibilityReportStore(tmp_path).get("../../outside")
```

Define stage codes `LOCAL_ENV`, `OLT_CONNECT`, `OLT_AUTOFIND`, `OLT_CURRENT_STATE`, `ONU_WEB_WAN`, `ONU_WEB_PING_PAGE`, `PC_INTERFACE`, `PC_PING`. Assert stored evidence paths are relative and reports contain no secret values.

```python
@dataclass(frozen=True)
class CreateCompatibilityCheck:
    olt_host: str
    olt_port: int
    expected_host_key_fingerprint: str
    olt_username_ref: str
    olt_password_ref: str
    onu_serial_number: str | None
    frame: int | None
    slot: int | None
    pon_port: int | None
    ont_id: int | None
    onu_web_url: str
    onu_web_username_ref: str
    onu_web_password_ref: str
    onu_adapter_key: str
    pc_interface_name: str
    pc_source_address: str
    pc_ping_target: str


@dataclass(frozen=True)
class CompatibilityStage:
    code: StageCode
    status: StageStatus
    message: str
    evidence: tuple[ArtifactPayload, ...] = ()


@dataclass(frozen=True)
class CompatibilityCheckView:
    check_id: str
    lifecycle: Lifecycle
    overall_status: OverallStatus | None
    stages: tuple[CompatibilityStage, ...]
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 2: Add safe generic artifact registration**

Test and implement `GeneratedEvidenceWriter.register_artifact(relative_path, payload)`. It requires content, rejects traversal, validates PNG signatures, preserves `redacted`, writes below root, and returns SHA256/size metadata.

```python
def register_artifact(self, relative_path: str, payload: ArtifactPayload) -> ArtifactPayload:
    if payload.content is None:
        raise ValueError("Artifact content is required")
    relative = self._safe_relative(relative_path)
    if payload.media_type == "image/png" and not payload.content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Screenshot must be PNG data")
    path = self._absolute(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload.content)
    return self._payload(path, payload.media_type, payload.content, payload.redacted)
```

- [ ] **Step 3: Run store/evidence tests and confirm RED**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_lab_compatibility_store.py backend\tests\test_local_runner_evidence.py -q --basetemp data\pytest-compat-store-red
```

- [ ] **Step 4: Implement atomic reports and evidence materialization**

Use `local_runner_evidence_root/lab-compatibility/<uuid>/`. Write `report.json.tmp`, close it, then replace `report.json`. Serialize explicit contract dictionaries only: no `SecretValue`, plaintext, absolute root, or command text.

```python
def save(self, view: CompatibilityCheckView) -> None:
    target = self._check_directory(view.check_id) / "report.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(view.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(target)
```

- [ ] **Step 5: Write failing orchestration tests**

```python
def test_ready_requires_all_required_stages(service):
    view = service.execute(service.create(valid_command()).check_id)
    assert view.lifecycle == "COMPLETED"
    assert view.overall_status == "READY"


def test_partial_target_is_needs_input(service):
    check_id = service.create(command_with_only_slot()).check_id
    view = service.execute(check_id)
    assert view.stage("OLT_CURRENT_STATE").status == "NEEDS_INPUT"
    assert view.overall_status == "PARTIAL"


def test_second_active_check_is_rejected(service):
    service.create(valid_command())
    with pytest.raises(ActiveCompatibilityCheckExists):
        service.create(valid_command())
```

Cover missing credentials, unwritable evidence root, OLT timeout/parser failure, unregistered SN, absent WAN, ONU selector mismatch, missing PC interface, localized Ping, secret redaction, and downstream `NOT_RUN` after a blocking prerequisite.

- [ ] **Step 6: Implement orchestration and overall status**

```python
def overall_status(stages):
    if any(stage.status == "BLOCKED" for stage in stages):
        return "BLOCKED"
    if all(stage.status == "VERIFIED" for stage in stages):
        return "READY"
    return "PARTIAL"
```

Persist after every stage. Preview and compare the OLT host key before resolving OLT credentials; resolve other credential references only when their adapter begins. OLT uses `write_text_and_png`, ONU uses `register_artifact`, PC Probe uses a check-scoped evidence base. Known adapter errors become Chinese instructions. Always release the single-active-check lock in `finally`.

Map ONU adapter `PASS` to `VERIFIED` and adapter `BLOCKED` to compatibility `BLOCKED`. Map PC `WAITING_OPERATOR` to `NEEDS_INPUT`, PC `PASS` to `VERIFIED`, and PC `FAIL/BLOCKED` to compatibility `BLOCKED`; none of these mappings creates a product result.

- [ ] **Step 7: Run tests and commit**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_lab_compatibility_store.py backend\tests\test_lab_compatibility_service.py backend\tests\test_local_runner_evidence.py backend\tests\test_pc_probe.py -q --basetemp data\pytest-compat-service
git add backend/app/lab_compatibility backend/app/local_runner/evidence.py backend/tests/test_lab_compatibility_store.py backend/tests/test_lab_compatibility_service.py backend/tests/test_local_runner_evidence.py
git commit -m "feat(lab): orchestrate compatibility checks and evidence"
```

---

### Task 4: 暴露仅限本机的 API

**Files:**
- Create: `backend/app/lab_compatibility/schemas.py`
- Create: `backend/app/lab_compatibility/router.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_lab_compatibility_api.py`

**Interfaces:**
- `POST /api/lab-compatibility-checks/host-key-preview`
- `POST /api/lab-compatibility-checks`
- `GET /api/lab-compatibility-checks/{check_id}`
- `GET /api/lab-compatibility-checks/{check_id}/evidence`
- `create_app(settings: Settings | None = None, *, credential_resolver: CredentialResolver | None = None, lab_compatibility_service: LabCompatibilityService | None = None) -> FastAPI` for deterministic tests.

- [ ] **Step 1: Write failing API contract tests**

```python
def test_create_accepts_references_only_and_returns_202(client):
    response = client.post("/api/lab-compatibility-checks", json=valid_payload())
    assert response.status_code == 202
    assert response.json()["lifecycle"] in {"PENDING", "RUNNING"}
    assert "secret-value" not in response.text


def test_routes_require_loopback(client_bound_to_all_interfaces):
    response = client_bound_to_all_interfaces.post(
        "/api/lab-compatibility-checks", json=valid_payload()
    )
    assert response.status_code == 403
```

Cover fingerprint preview/confirmation, changed fingerprint blocking before credentials/commands, all-or-none target fields, invalid SN, public OLT IP, remote/credential-bearing ONU URL, unavailable credentials, unknown UUID, active-check 409, `Cache-Control: no-store`, and secret scanning.

- [ ] **Step 2: Run API tests and confirm RED**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_lab_compatibility_api.py -q --basetemp data\pytest-compat-api-red
```

- [ ] **Step 3: Implement schemas, loopback guard, and background execution**

```python
class CompatibilityCheckCreate(BaseModel):
    olt_host: IPvAnyAddress
    olt_port: int = Field(default=22, ge=1, le=65535)
    expected_host_key_fingerprint: str
    olt_username_ref: str
    olt_password_ref: str
    onu_serial_number: str | None = None
    frame: int | None = Field(default=None, ge=0, le=15)
    slot: int | None = Field(default=None, ge=0, le=31)
    pon_port: int | None = Field(default=None, ge=0, le=255)
    ont_id: int | None = Field(default=None, ge=0, le=127)
    onu_web_url: AnyHttpUrl
    onu_web_username_ref: str
    onu_web_password_ref: str
    onu_adapter_key: Literal["neutral-v1"] = "neutral-v1"
    pc_interface_name: str
    pc_source_address: IPvAnyAddress
    pc_ping_target: str
```

Add model validators for complete target and private/local addresses. `POST` writes PENDING first, schedules `service.execute(check_id)` with `BackgroundTasks`, and returns 202. Initialize one service on `application.state`, register router under `/api`, and return no-store headers.

- [ ] **Step 4: Run tests and commit**

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_lab_compatibility_api.py backend\tests\test_local_credential_api.py backend\tests\test_health.py -q --basetemp data\pytest-compat-api
git add backend/app/lab_compatibility backend/app/core/config.py backend/app/main.py backend/tests/test_lab_compatibility_api.py
git commit -m "feat(lab): expose loopback compatibility API"
```

---

### Task 5: 构建中文“现场检查”页面

**Files:**
- Create: `frontend/src/labCompatibility/types.ts`
- Create: `frontend/src/labCompatibility/api.ts`
- Create: `frontend/src/labCompatibility/api.test.ts`
- Create: `frontend/src/labCompatibility/LabCompatibilityPage.tsx`
- Create: `frontend/src/labCompatibility/LabCompatibilityPage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Produces `LabCompatibilityApi.previewHostKey`, `.credentialStatus`, `.enrollCredential`, `.createCheck`, `.getCheck`, `.listEvidence`.
- Produces `LabCompatibilityPage({ api })`.
- Sends secrets only to `/api/local-credentials`; check request contains references only.

- [ ] **Step 1: Write failing API client tests**

```typescript
it("sends only credential references when creating a check", async () => {
  await api.createCheck(validInput);
  const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
  expect(body.olt_password_ref).toBe("olt.lab.password");
  expect(JSON.stringify(body)).not.toContain("secret-value");
});
```

Test URL encoding, 409 messaging, 422 field errors, and polling termination.

- [ ] **Step 2: Write failing four-step page tests**

```tsx
it("states the safety boundary", () => {
  render(<LabCompatibilityPage api={fakeApi()} />);
  expect(screen.getByText(/不会注册 ONU/)).toBeInTheDocument();
  expect(screen.getByText(/不会下发 WAN/)).toBeInTheDocument();
  expect(screen.getByText(/不会修改 OLT 配置/)).toBeInTheDocument();
});


it("requires confirmation of the previewed host key", async () => {
  render(<LabCompatibilityPage api={fakeApi()} />);
  await fillTargetsAndPreviewFingerprint();
  expect(screen.getByRole("button", { name: "开始只读检查" })).toBeDisabled();
  fireEvent.click(screen.getByLabelText("我已核对 OLT 主机指纹"));
  expect(screen.getByRole("button", { name: "开始只读检查" })).toBeEnabled();
});
```

Cover clearing secret inputs, optional target fields, duplicate-click prevention, four stage labels, three overall statuses, Chinese guidance, evidence names/hashes, absence of formal PASS/FAIL wording, and navigation to existing modules.

- [ ] **Step 3: Run frontend tests and confirm RED**

```powershell
Set-Location frontend
npm.cmd test -- src/labCompatibility/api.test.ts src/labCompatibility/LabCompatibilityPage.test.tsx src/App.test.tsx --reporter=dot --maxWorkers=1
Set-Location ..
```

- [ ] **Step 4: Implement typed client and four-step page**

```typescript
export type StageStatus = "VERIFIED" | "NEEDS_INPUT" | "BLOCKED" | "NOT_RUN";
export type OverallStatus = "READY" | "PARTIAL" | "BLOCKED";
export type Lifecycle = "PENDING" | "RUNNING" | "COMPLETED";
```

Sections are “填写目标”“检查凭据”“执行检查”“查看报告”. Preview the host key before enabling run. Poll every 750 ms only while PENDING/RUNNING, cancel on unmount, disable duplicate start, and clear enrolled secret state after its request.

```typescript
useEffect(() => {
  if (!check || check.lifecycle === "COMPLETED") return;
  const timer = window.setTimeout(async () => {
    setCheck(await api.getCheck(check.check_id));
  }, 750);
  return () => window.clearTimeout(timer);
}, [api, check]);
```

- [ ] **Step 5: Integrate and style the module**

Add “现场检查” to `App.tsx`, inject its API through `AppProps`, and keep “设备库” as default. Reuse existing cards, forms, status chips and responsive breakpoints; use neutral/amber/red compatibility states, not product PASS/FAIL colors.

```tsx
<button
  type="button"
  className={activeModule === "lab-compatibility" ? "active" : ""}
  onClick={() => setActiveModule("lab-compatibility")}
>
  现场检查
</button>
```

- [ ] **Step 6: Run frontend tests/build and commit**

```powershell
Set-Location frontend
npm.cmd test -- --reporter=dot --maxWorkers=1
npm.cmd run build
Set-Location ..
git add frontend/src
git commit -m "feat(lab): add read-only compatibility wizard"
```

---

### Task 6: 全量验证、说明和现场准备

**Files:**
- Create: `docs/ONU_LAB_COMPATIBILITY_CHECK.md`
- Modify: `docs/superpowers/plans/2026-09-18-onu-registration-dual-wan-skill.md`
- Modify only when verification exposes a defect: files owned by Tasks 1–5.

**Interfaces:**
- Produces a safe operator runbook and automated validation baseline.
- Does not connect to real OLT/ONU until the user supplies and confirms现场参数。

- [ ] **Step 1: Document inputs and safety behavior**

List host/port, host-key confirmation, four credential references, optional SN and complete target, ONU Web URL, adapter, PC interface/source/Ping target, evidence location, statuses, and retry instructions. Include:

```text
现场兼容性检查不会注册或删除 ONU，不会下发或删除 WAN，不会修改 service-port，
不会执行 ONU Web Ping，也不会把检查结果写成产品 PASS/FAIL。
```

- [ ] **Step 2: Link this plan before original Task 8**

Add a checkpoint to the main plan requiring this supplemental plan and its first real report review before the formal coordinator or mutation path. Do not renumber original tasks.

- [ ] **Step 3: Run safety scans**

```powershell
rg -n "register_ont|delete_ont|provision_ipoe|provision_pppoe|remove_service_port" backend/app/lab_compatibility
rg -n "192\.168\.87\.204|48575443DD91BBBB" backend/app/lab_compatibility frontend/src/labCompatibility docs/ONU_LAB_COMPATIBILITY_CHECK.md
```

Expected: mutation names only in deny-list/security text or tests, never an executable dispatch map; no fixed lab target or credential.

- [ ] **Step 4: Run full verification**

```powershell
.\.venv\Scripts\python -m pytest backend\tests -q --basetemp data\pytest-compat-final
Set-Location frontend
npm.cmd test -- --reporter=dot --maxWorkers=1
npm.cmd run build
Set-Location ..
git diff --check
```

Expected: zero test failures, successful production build, and clean diff check.

- [ ] **Step 5: Perform a fake-adapter UI smoke check**

Start existing development servers with an injected fake service, open “现场检查”, verify four steps, duplicate-click protection and generated report. Do not enter real device addresses.

- [ ] **Step 6: Commit the validated checkpoint**

```powershell
git add docs backend frontend
git commit -m "docs(lab): finalize compatibility-check runbook"
```

- [ ] **Step 7: Request现场参数 before the first real check**

Request OLT private IP/port, confirmation of displayed fingerprint, credential reference names, ONU Web URL, optional SN and complete F/S/P/ONT ID, and PC interface/source/Ping target. Run only the read-only page after confirmation. Review `READY/PARTIAL/BLOCKED` together before returning to the formal Skill plan.

## Final Validation Gates

- `lab_compatibility` has no mutation dispatch path and rejects unknown actions before the command channel.
- Host-key preview requires explicit confirmation; fingerprint mismatch blocks before authentication or commands.
- ONU Web compatibility never invokes `run_ping` or WAN save.
- PC checks bind to the selected source and leave Windows network configuration unchanged.
- Reports contain only references, redacted evidence, relative paths and SHA256 values.
- API is unavailable under non-loopback binding.
- No compatibility run creates or updates formal test-management rows.
- UI never labels compatibility as product PASS/FAIL.
- Full backend/frontend tests and production build pass before a real connection.
- Configuration-changing Skill execution remains prohibited until the user reviews the compatibility report.
