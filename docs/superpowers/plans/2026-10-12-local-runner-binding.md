# Local Runner Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Task 9 API 接到本机配置及成对系统凭据，调用已有 ONU/OLT/PC 适配器，安全产出事实和 Evidence。

**Architecture:** 配置加载与凭据解析独立；创建会话时将非敏感绑定固定到已有 plugin_snapshot。应用级工厂只持有配置和解析器，执行前从会话快照创建绑定 Runtime；Coordinator 继续负责审批、状态、证据保存与最终判定。

**Tech Stack:** Python >=3.12、FastAPI、Pydantic、SQLAlchemy/SQLite、keyring、Paramiko、Playwright、Pillow、pytest；复用现有依赖，不新增依赖或迁移。

**Spec:** `docs/superpowers/specs/2026-10-12-local-runner-binding-design.md`（用户 2026-10-12 确认）。

**Base:** f03a60a20b1a61d84d46d88caa84011241a19035，分支 codex/skill-execution，现有隔离 worktree；main 不修改。

## Global Constraints

- 本机非敏感配置文件加 Windows 系统凭据存储，支持换电脑。不增加数据库表、业务模块或测试范围；保持 DEVELOPMENT、单进程、仅 loopback 访问。
- 不开发 Task 10 前端，不合并或推送，不将设计批准视为现场操作授权。
- schema_version=1，extra 字段禁止；初始化只读取配置，不连接设备。
- 绑定对象创建后不可修改，不改既有 Device、Case、Environment、parameter_snapshot 或 standard_snapshot 内容，不需要迁移。
- Run/Result 不自动 LOCK。RESTORE 仅在完整恢复可验证时成功，否则 MANUAL_REQUIRED，禁止扩大恢复承诺。
- 测试替身仅替换外部 I/O；不访问真实设备，不在 Git/配置/事件/证据中写入账号密码。

## Review Focus

1. JSON 重复键及未知字段不能静默覆盖目标（Task 1）。
2. 配置更新/重启后，恢复旧会话不能使用新目标或新凭据映射（Tasks 2、6）。
3. known_hosts 已有条目不能绕过固定 SSH 指纹（Task 3）。
4. DHCP 多地址、多网卡、并发 WAN 下，无法证明探测归属不能 PASS（Task 4）。
5. 等待接线不得意外进入异常恢复；仅注册信息相等不能证明完整 WAN 已恢复（Tasks 4、6）。

## 文件与职责

新增 `backend/app/local_runner/configuration.py`（严格配置/绑定类型）、`access.py`（成对凭据）、`runtime.py`（工厂/绑定 Runtime）、`facts.py`（标准事实组合）、`setup.py`（本机隐藏输入配置工具）。新增 `backend/config/local-runner.example.json`、`docs/LOCAL_RUNNER_SETUP.md` 及对应测试。

小范围修改 `core/config.py`、`main.py`、`skill_execution/service.py`、`skill_execution/router.py` 和 `local_runner/ma5800/transport.py`。仅必要时扩展现有适配器的超时/关闭边界，不重构旧业务模块。保留 `.gitignore` 已有 data 排除规则。

## 通用 TDD 与命令

以下命令在 worktree 根执行；先设置 `$env:PYTHONPATH = (Join-Path (Get-Location) 'backend')`。每次运行用新的短临时路径，例如 `C:/Users/admin/Documents/Codex/lrb-t1-red-1012`，不得重用承载非测试数据的 basetemp。

每个任务按 RED → 最小实现 → GREEN → 全量后端回归 → 提交；确认 RED 是所述行为失败或新模块缺失，不是环境权限/路径错误。全量命令：`python -m pytest backend/tests -q -p no:cacheprovider --basetemp=<本次唯一短路径>`；提交前 `git diff --check` 和检查实际文件清单，禁止 `git add .`。最终前端验证在 frontend 目录执行 `npm.cmd test -- --reporter=dot --maxWorkers=1`、`npm.cmd run build`。

测试公共样本：在 `backend/tests/local_runner_binding_fixtures.py` 提供 `valid_config()`，返回严格配置 dict，引用为 lab.olt/lab.onu 和 lab.olt.access/lab.onu.access/lab.ppp.access，示例私网地址 10.20.0.2 与 http://10.20.1.1，网卡 Fixture Ethernet，指纹由测试公钥生成。六条 leaf refs 对应三对 username/password；FakeCredentialStore 只保存测试值。创建会话沿用 `test_skill_execution_repository.execution_fixture` 的真实 SQLite/catalog/device/environment，替换其目标和访问引用匹配该样本。不在测试中初始化实际 keyring、SSH 或浏览器。

### Task 1: 严格配置与本机凭据初始化

**Files:** Create configuration.py、access.py、setup.py、示例 JSON、LOCAL_RUNNER_SETUP.md、tests/local_runner_binding_fixtures.py、tests/test_local_runner_configuration.py、tests/test_local_runner_access.py、tests/test_local_runner_setup.py；Modify core/config.py。

**Interfaces:** `load_runner_config(path: Path) -> RunnerConfig`；`RunnerConfig` 为 frozen/extra-forbid 类型，具有 schema_version、enabled、targets、access_bindings。`AccessBinding(kind, username_ref, password_ref)`；`PairedAccessResolver(config: RunnerConfig, resolver: CredentialResolver)`，提供 `available(reference: str) -> bool`、`resolve(reference: str, expected_kind: str) -> tuple[SecretValue, SecretValue]`。校验异常 `RunnerConfigurationError(ValueError)`，错误只含安全码。

- [ ] **RED 测试。** 以真实 JSON 文件验证以下断言：
  ```python
  def test_extra_and_duplicate_target_keys_are_rejected(tmp_path):
      with pytest.raises(RunnerConfigurationError):
          load_runner_config(write_config_with_duplicate_target(tmp_path))

  def test_pair_requires_both_leaves(access_case):
      assert access_case.pairs.available('lab.olt.access') is False
      access_case.enroll_test_pair('lab.olt.access')
      assert access_case.pairs.available('lab.olt.access') is True
  ```
  `write_config_with_duplicate_target` 在本测试文件写固定的重复 lab.olt 键；`access_case` 用共享 valid_config 和 FakeCredentialStore。另测公网/回环/组播/未指定 IP、URL 用户信息、端口越界、未知 adapter、引用格式/同一 leaf/错误 kind、配置中出现 password、非法 JSON/编码及不可读文件；异常不回显输入。setup 测试断言终端输出/生成文件不含测试账号密码，非交互输入拒绝且不写凭据。
- [ ] **验证 RED。** `python -m pytest backend/tests/test_local_runner_configuration.py backend/tests/test_local_runner_access.py backend/tests/test_local_runner_setup.py -q`，确认新接口缺失或断言失败。
- [ ] **最小实现。** 添加 Settings.local_runner_config_path: str | None = None；JSON 用 object_pairs_hook 拒绝重复键。enabled=false 可用空目标/映射；显式路径非法即报错，enabled=true 要求完整配置。设备 IP 严格私网单播；ONU URL 禁止 fragment/query/用户信息，adapter_key 仅 neutral-v1。规范化白名单字典用 sorted keys、紧凑 JSON、UTF-8 计算 SHA256。
- [ ] **本机工具。** `setup.main(argv: Sequence[str] | None = None) -> int`；命令 `python -m app.local_runner.setup --config <文件> --access-ref <逻辑引用>`。只接受已存在映射，用 getpass 隐藏读取账号和密码，调用 Resolver.enroll；不接受 secret 命令行参数，不联网。单次入库任一失败则回滚该对的新值/保留旧值，明确失败退出。示例 JSON 默认 enabled=false，空 maps，不带实验室地址或凭据。
- [ ] **GREEN 与提交。** 重跑三文件及后端全量；显式添加本任务文件，提交 `feat(runner): add local configuration and paired credentials`。

### Task 2: 会话固定绑定与历史兼容

**Files:** Modify configuration.py、skill_execution/service.py；Create tests/test_local_runner_binding.py。

**Interfaces:** frozen `RuntimeBinding(version=1, config_sha256, olt_target_ref, onu_web_target_ref, olt, onu, access_bindings)`；olt/onu 复制已校验目标字段，access_bindings 按 OLT/ONU_WEB/PPPOE 保存 leaf refs。`resolve_runtime_binding(config: RunnerConfig, parameters: Mapping[str, Any], pairs: PairedAccessResolver) -> RuntimeBinding`；`SkillExecutionService.__init__(..., binding_resolver: Callable[[Mapping[str, Any]], RuntimeBinding] | None = None)`。

- [ ] **RED 测试。** `test_binding_is_saved_in_creation_transaction` 断言 plugin_snapshot.runtime_binding.version==1、olt.host=='10.20.0.2'、不存在测试账号密码；`test_invalid_binding_creates_no_run` 断言错目标/错类型/缺 leaf 时 Run、Result、Session 数量不增加；`test_config_change_does_not_change_persisted_binding` 保存原绑定，改新 config 为 10.20.0.3 后断言旧绑定仍为 10.20.0.2、旧 parameter/standard/environment snapshots 字节内容不变。
- [ ] **验证 RED。** `python -m pytest backend/tests/test_local_runner_binding.py -q`。
- [ ] **最小实现。** 在现有参数合并/校验后、事务提交前解析绑定并写 plugin_snapshot 子对象。未配置 binding_resolver 时保留低层 Service 离线调用兼容性；正式 API 的未配置保护由 Task 6 控制。绑定不可变，不暴露公开响应，不追溯补写旧会话。引用仅指向已配置种类，校验当前凭据可用但不保存值。
- [ ] **GREEN 与提交。** 跑本文件、原 repository/API 测试及后端全量；提交 `feat(runner): freeze runtime bindings at execution creation`。

### Task 3: 每条 SSH 连接验证固定指纹

**Files:** Modify local_runner/ma5800/transport.py；Create tests/test_local_runner_pinned_connection.py。

**Interfaces:** 保持 `MA5800SSHConnector.connect(...)` 参数不变；实际会话公钥必须始终与 expected_fingerprint 匹配，错指纹抛已有 HostKeyFingerprintMismatchError，资源关闭。

- [ ] **RED 测试。** `test_known_hosts_cannot_bypass_pin`：外部 SSHClient 替身模拟 known_hosts 命中但实际公钥 B，与配置公钥 A 不同，断言连接被拒绝、无 invoke_shell；另测未知主机匹配成功、不匹配拒绝、认证/连接/验证异常均关闭 client，不更新系统 known_hosts，不输出测试密码。
- [ ] **验证 RED。** `python -m pytest backend/tests/test_local_runner_pinned_connection.py -q`，预期现有 known_hosts 命中路径未复核而失败。
- [ ] **最小实现。** 复用现有固定指纹 policy，并在已连接 transport 上再验证实际公钥后才返回可执行 client；读取失败同样关闭并拒绝。不自动接受新指纹、不做双连接预览替代校验、不取消 Paramiko 原校验。
- [ ] **GREEN 与提交。** 跑本文件、现有 transport 测试及全量后端；提交 `fix(runner): enforce pinned keys on every SSH connection`。

### Task 4: 已绑定 Runtime、事实与证据

**Files:** Create runtime.py、facts.py、tests/test_local_runner_runtime.py、tests/test_local_runner_facts.py；Modify local_runner/pc_probe.py 的网卡枚举以携带真实前缀长度，兼容原构造参数；其他必要的小范围适配器改动必须先有 RED 测试。

**Interfaces:** `LocalRuntimeFactory(config: RunnerConfig, resolver: CredentialResolver, resources: RuntimeResources | None = None)`；`.available(reference: str) -> bool`；`.resolve_binding(parameters: Mapping[str, Any]) -> RuntimeBinding`；`.for_binding(binding: RuntimeBinding, history_reader: Callable[[], Sequence[ExecutionEvent]]) -> BoundExecutionRuntime`。`RuntimeResources` 构造 SSH/ONU surface、网卡 provider、PCProbe、时钟；生产默认调用现有真实实现，测试仅替换这些外部边界。

`BoundExecutionRuntime.secrets_for(parameters: dict, action: str) -> dict[str, SecretValue]`、`.execute(context: ActionContext) -> ActionOutcome` 与现有 Coordinator 签名一致。绑定 Runtime 不读取当前 config，也不缓存 SecretValue；history_reader 提供该会话有序持久化事件（ExecutionEvent 为已有 models.execution_session 类型）。

`facts.derive_standard_facts(action: str, parameters: Mapping[str, Any], observations: Sequence[Observation], history: Sequence[ExecutionEvent]) -> tuple[Observation, ...]`：只产出既有六个标准 bool 及已支持的有限数字 Ping 指标；缺少来源时不产出对应 bool，真实不匹配产出 False。函数纯计算，不联网或写 DB。InterfaceAddress 新增 prefix_length: int | None = None，Windows 枚举读取 PrefixLength；未知前缀不得猜测子网。

- [ ] **RED 测试。** `test_runtime_uses_frozen_binding_not_current_config` 断言实际 connector 目标始终 10.20.0.2；`test_wrong_or_unknown_action_has_no_external_effect` 断言 BLOCKED 且 connector 未调用。表驱动事实测试：匹配/不匹配/缺字段分别 True/False/不存在；status=PASS 但无来源时所有标准 bool 不存在；另一 WAN 地址/Ping、旧 attempt 的响应、非有限数字不得产生当前 WAN PASS。
- [ ] **归属与恢复测试。** `test_pc_requires_unique_bound_interface_address` 在 0/2 个候选、未知 prefix_length 和其他 NIC 成功样本下断言 WAITING_OPERATOR/无联网 True；`test_partial_restore_never_becomes_verified` 用只有 registration 的配置快照断言禁止自动恢复变更、恢复核验返回 BLOCKED，不能生成完整恢复事实。`test_resources_close_on_timeout_or_selector_failure` 验证外部资源关闭、安全错误码和可取得证据，无 secret 泄露。
- [ ] **验证 RED。** `python -m pytest backend/tests/test_local_runner_runtime.py backend/tests/test_local_runner_facts.py -q`。
- [ ] **最小接线。** OLT 使用 MA5800Actions/LocalActionRegistry；Web 仅 capture_onu_wan/run_onu_ping、neutral-v1；PC 仅 pc_connectivity_probe。连接只在动作调用时建立。OLT executor 捕获 CommandTranscript.normalized_output（解析可用）并用 GeneratedEvidenceWriter.write_text_and_png 脱敏生成 TXT/PNG；不保存命令原文。PC 地址由绑定网卡实时枚举，唯一候选须与 ONU IP 所在本机子网相符；不可证明匹配则等待，不猜 /24、不切路由。
- [ ] **事实规则。** SN/FSP/ONT/Profile/online/match 来自对应 parsed OLT 数据；地址验证须同 WAN/VLAN 的 OLT/Web 可用状态及相同有效单播地址；联网须本次该 WAN ONU Ping 全部成功与绑定 PC 同样成功且隔离可证明。任何额外阈值必须来自固定标准，否则不增加。通用系统 DNS/默认路由成功不能充当归属证明。
- [ ] **等待与结束。** PC WAITING_OPERATOR 封装现有带精确 preview_hash 的 interaction 协议，目标及提示明确“接线确认，非配置修改授权”，不将缺 preview 转为异常恢复。按 durable ACTION_STARTED 的 ref 区分初始 SNAPSHOT 与 RESTORE_VERIFY，不依据请求猜阶段。完整 WAN 恢复不可证时在恢复及核验两阶段均返回 BLOCKED，留给已有 MANUAL_REQUIRED 流程；注册相等不够。
- [ ] **GREEN 与提交。** 跑两文件、已有 Web/PC/actions/coordinator 测试和全量后端；提交 `feat(runner): compose bound execution and evidence facts`。

### Task 5: 应用与 API 接线

**Files:** Modify main.py、skill_execution/router.py、skill_execution/service.py；Create tests/test_local_runner_binding_api.py；Modify 原 API 测试 Runtime 替身以明确提供工厂契约（不在产品类中增加测试专用路径）。

**Interfaces:** 扩展可信注入契约为 Task 4 工厂；Service 构造器新增 runtime_factory: LocalRuntimeFactory | None = None，保留 Task 2 的 binding_resolver；`build_service(...)` 同时注入工厂与其 resolve_binding。Service 的既有 `advance(session_id)`/`respond(session_id, interaction_id, response)` 在 Coordinator 改状态前调用 `_bind_runtime(session_id)`，从 DB 获取并严格验证旧 binding，再将新 BoundExecutionRuntime 的 execute/secrets_for 设置为本请求 Coordinator 回调，history_reader 固定该 session。无全局“当前会话”或跨请求共享回调。

- [ ] **RED 测试。** `test_create_persists_binding_without_network` 断言 201 且外部连接次数 0；`test_unconfigured_create_rejects_before_run` 断言 API 在无配置/未启用 Runtime 时 422 且无新 Run；`test_legacy_session_readable_but_cannot_advance` 断言 GET 200、advance/respond 409 且无事件/状态改变、无连接。`test_restart_uses_old_binding_after_config_change` 将 config 改为新目标后重建 app，旧会话仍只使用旧目标和旧 leaf refs；缺旧 leaf 返回安全阻塞，不降级到新映射。
- [ ] **审批/恢复测试。** 真实 Service/Coordinator，fake 外部 I/O：未批准/过期 hash 不执行设备配置；接线 WAITING 保持可恢复，不产生异常 MANUAL_REQUIRED；RUNNING 重启按现有流程恢复，不调用任何动作；部分恢复不能 VERIFIED；接口、事件、文件、下载、日志不含测试 secret；公共视图不输出 binding/path/leaf refs。
- [ ] **验证 RED。** `python -m pytest backend/tests/test_local_runner_binding_api.py -q`。
- [ ] **最小实现。** main 在 app 构造期只加载配置及构造工厂；显式可信注入供测试，生产 default None + 配置路径决定是否启用。错误配置启动报安全异常；不探测设备。创建时严格 binding，错误映射 422；旧会话缺绑定映射 409，detail 安全码 RUNTIME_BINDING_REQUIRED；不改变现有请求 schema 或增加 HTTP 配置 API。保留 loopback/origin/no-store/LOCKED/snapshot/活动冲突保护。
- [ ] **GREEN 与提交。** 跑新 API 文件、原 Task 9 API/coordinator 测试和全量后端；提交 `feat(skill): connect local runtime through frozen bindings`。

### Task 6: 离线闭环验收与使用说明

**Files:** Create tests/test_local_runner_binding_acceptance.py、docs/LOCAL_RUNNER_BINDING_ACCEPTANCE.md；Update LOCAL_RUNNER_SETUP.md、ONU_SKILL_TASK9_IMPLEMENTATION.md。

**Interfaces:** 不新增产品接口；通过现有 create/advance/respond/evidence/download 驱动真实本机工厂、Service/Coordinator 与数据库，仅外部 I/O 使用场景替身。

- [ ] **RED 验收测试。** `test_api_to_runtime_to_evidence_chain` 遍历已注册/新注册、IPoE/PPPoE 成功及失败、旧会话/缺 leaf、错误公钥、错误网卡、Web selector 失败，断言可回溯的标准事实/事件/hash/证据归属，未批准零变更；DRAFT 不自动 LOCK。`test_interrupted_mutation_is_not_replayed` 断言重启无配置动作、保留历史证据并进入恢复。以需要完整已授权证据的样本证明 SUCCESS；只支持部分恢复的样本必须 MANUAL_REQUIRED，不为了 PASS 改标准或添加假事实。
- [ ] **验证 RED。** `python -m pytest backend/tests/test_local_runner_binding_acceptance.py -q`；若实现已满足某样本则保留该兼容性测试，不声称其经历 RED；缺失行为须先失败再最小修复，不增加新测试项。
- [ ] **说明。** 写配置/leaf enrollment/启停/网卡更新/换电脑/指纹人工复核/旧 Run 不能补绑定/手工恢复步骤；说明系统凭据不随数据库迁移。验收记录区分离线替身结果与真实 DUT，真实部分标记 NOT_EXECUTED，不能填写虚构 PASS。
- [ ] **最终验证。** 后端全量 pytest、前端 test（单 worker）、build、git diff --check；扫描本次变更无 db、Evidence、ZIP、密码、缓存或产物。执行方式选择 Native 时做一次全分支独立只读审核；先修 Critical/Important，再复跑受影响验证及全量。提交 `test(runner): verify local binding execution and recovery gates`。
- [ ] **停止与交付。** 列修改文件/测试/风险/commit/Git 状态；保留 worktree，不合并或推送。另行申请真实现场验收，重新确认设备与实验室参数、逐次审批配置变更；没有该授权不扫描 IP、不预览公钥、不登录设备。

## 计划自检与交接

设计 1–3 节由 Tasks 1、3 实现；绑定不漂移由 Tasks 2、5 实现；Runtime/事实/E1–E6/恢复边界由 Tasks 4–6 实现。五个 Review Focus 均有指定测试。只有现有 JSON 的 additive 字段，无 Migration；现场配置不会写进仓库。历史标准不变、缺来源 BLOCKED 与默认不执行的约束一致。

当前只写计划，未开始任一任务。请先审核计划并选择 Native（本会话逐任务实施，最后独立审核）或 Subagent-driven（每任务独立实施及审核）。六项任务共享紧密的绑定/Runtime 契约，建议 Native，避免逐任务重复读取上下文；真实设备验收仍单独授权。
