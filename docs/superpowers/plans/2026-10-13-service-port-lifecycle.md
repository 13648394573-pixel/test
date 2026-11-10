# service-port Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留已有 ONU 注册，精确复用或经审批创建业务端口，只清理本次创建的资源。

**Architecture:** 新增小型映射契约和事件账本模块，Runner 负责白名单读取/写入及证据，Coordinator 负责审批、短事务和动作推进。新计划显式版本化；旧计划与快照不改写。完整 WAN 恢复继续受保护。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy、SQLite、Pydantic、pytest；现有 MA5800 SSH 与 EvidenceStorage。无新增依赖或数据库迁移。

**Spec:** docs/superpowers/specs/2026-10-13-service-port-lifecycle-design.md（用户已书面批准）；实施基线 ae11ecfe98dfe30567f12c84ad19aa1a292e24d0。

## Global Constraints

- 单机 B/S、DEVELOPMENT、现有隔离分支 codex/skill-execution；不修改 main、不合并、不推送。
- 不修改旧 Run、Result、Snapshot、LOCKED 规则；不自动升级旧执行计划。
- 不新增数据库表、独立前端业务模块、LAN/NAT/DNS 功能测试或完整 WAN 自动恢复；2026-10-14 用户允许 Task 7 最小接入现有测试执行页的审批展示与确认。
- 匹配则复用，缺失才创建；REUSED 永不自动删除，CREATED 需本会话已核验归属。
- 未经具体现场审批不连接设备；本计划批准不授权注册、删除或 WAN 下发。
- 先持久化意图，再设备 I/O，再后验与短事务；不将设备写入视为数据库可回滚事务。
- 每项测试必须先 RED 再 GREEN；阶段完成后给出文件、测试、风险结果，提交前等待用户指令。

## Review Focus

1. 目标 ONT 列表为空但候选 ID 在别处占用：按全局 ID 查询，不得创建（Task 1/4）。
2. 审批后现场映射或身份改变：旧审批失效，零写入（Task 4）。
3. 两路 WAN 共用映射且切换其中一路：保留公共端口，不虚报隔离（Task 3/5）。
4. 设备已写入但 Evidence/数据库提交失败：进入不确定状态，不自动重试或认领（Task 4/6）。
5. 同 ID、同映射被外部删除重建：不能声称拥有永久所有权，漂移或身份不确定停止，存在无法观察的竞争窗口（Task 5/7）。

## 文件边界

- 新增 backend/app/local_runner/ma5800/service_port_contracts.py：完整映射、查询结果、操作与预览类型。
- 新增 backend/app/skill_execution/service_port_ledger.py：事件重放、消费者与清理资格，纯函数。
- 新增 backend/app/skill_execution/service_port_lifecycle.py：创建/清理的短事务编排，避免继续堆大 Coordinator。
- 修改 ma5800/transport.py、parsers.py、actions.py：明确参数的白名单命令、完整查询与单条动作。
- 修改 local_runner/configuration.py、runtime.py：配置冻结、绑定、动作注册及配置模式切换。
- 修改 skill_execution/coordinator.py、service.py、repository.py、schemas.py、router.py 与 skill_catalog/onu_registration_dual_wan.py：新计划、事件、只读摘要。
- 各 Task 下列新增测试独立；仅必要时调整旧测试替身，不能降低安全断言。
- 仅更新 docs/LOCAL_RUNNER_LIVE_ACCEPTANCE.md 和配置示例说明，不存真实地址、凭据、端口证据或数据库。

## 契约约定（各 Task 共用）

MappingSpec 为冻结类型：vlan:int（1..4094）、gemport:int（0..4095）、user_vlan:int（1..4094）、tag_transform:str、business_type:str、candidate_id:int|None（0..65535）；整数拒绝 bool。
ServicePortMapping 增加 olt_binding_hash:str、fsp:str（规范 F/S/P）、ont_id:int（0..127），完整属性缺失不接受。
PortRead 为冻结类型：status=FOUND/ABSENT/UNCONFIRMED、items:tuple[ServicePortDetail,...]、evidence_ids:tuple[str,...]、observation_hash:str；ServicePortDetail 包含 port_id:int、mapping:ServicePortMapping。
PortOperation 包含 operation_id、session_id、mapping、port_id、kind=CREATE/DELETE、baseline_hash、read_hash、creation_event_id（删除必填）。
PortPreview 包含以上完整信息及 preview_hash；规范 JSON 排序后 SHA256，排除密码与动态时间，不排除目标/操作/映射/证据范围。
OperationOutcome 为现有 ActionOutcome；observations 携带 operation_id、分类和后验，不让 Runner 直接写数据库。
以上 tag_transform/business_type 仅接受 Task 1 有可信离线命令与详情样本的值，其余明确拒绝；不从旧简表补默认值。

### Task 1：完整读取、配置契约与命令白名单

**Files:** 新增 service_port_contracts.py；修改 ma5800/parsers.py、transport.py、configuration.py；新增 backend/tests/test_service_port_contracts.py、test_service_port_detail.py；扩展 test_ma5800_transport.py、test_local_runner_configuration.py。
**Interfaces:** parse_service_port_detail(text:str, *, binding_hash:str) -> PortRead；读取目标清单沿用 parse_service_ports；新增 display_service_port_by_id/read_profile_gem/create_service_port 三种 SafeMA5800Command 编码。配置新增 RunnerConfig.service_port_profiles:dict[str,ServicePortProfile]（键为 OLT 目标引用），ServicePortProfile.ipoe/pppoe:MappingSpec|None；RuntimeBinding.service_port_profile:ServicePortProfile|None 创建时冻结。

- [x] 写 test_partial_detail_is_unconfirmed：简表有 ID/VLAN 但没有完整转换属性，断言 UNCONFIRMED；test_global_id_owned_elsewhere_is_found：断言非目标端口不被误判 ABSENT。
- [x] 写类型/配置测试：bool、越界 VLAN/GEM/ID、前导零 FSP、未知属性拒绝；旧配置不含新字段仍能加载；修改本机配置不改变既有冻结绑定。
- [x] 运行 `python -m pytest backend/tests/test_service_port_contracts.py backend/tests/test_service_port_detail.py -q`，确认新增断言失败。
- [x] 从已有可信脱敏记录/厂商命令参考固化详情、全局 ID 未占用、Profile/GEM 的样本和准确命令模式；不猜测不存在响应。若缺样本，只实现 UNCONFIRMED 并停止创建子任务，说明需要只读采集，未经授权不联网。
- [x] 实现严格解析与结构化编码；限定明确业务类型/转换值；创建命令拒绝任意 CLI，查询采用配置级上下文，不误在 GPON 子模式下运行。
- [x] 运行上述测试及 test_ma5800_transport.py、test_ma5800_service_ports.py、test_local_runner_configuration.py，全部 PASS；复查示例无现场数据。
- [ ] 阶段提交建议 `feat(local-runner): define verified service port mappings`，等待用户指令。

Task 1 验证：相关 143 passed，完整后端 680 passed；端口/设备参数已在 fixture 中虚构化。未接入可执行创建动作、未修改实际配置；整体独立审核仍待 Task 7。详细 TDD、范围裁定及只读样本记录见 docs/LOCAL_RUNNER_LIVE_ACCEPTANCE.md。

### Task 2：追加式资源账本

**Files:** 新增 service_port_ledger.py、backend/tests/test_service_port_ledger.py；必要修改 repository.py，仅复用现有事件表。
**Interfaces:** replay_port_ledger(session_id:str, events:Sequence[ExecutionEvent]) -> tuple[PortResource,...]；cleanup_candidates(resources:Sequence[PortResource], retained_consumers:frozenset[str]) -> tuple[PortResource,...]。PortResource 包含映射、ID、origin、消费者、创建事件引用、状态和最后证据；未知事件版本或非法状态序列拒绝，不跳过。

- [x] 写 test_only_verified_session_created_resources_are_cleanup_candidates，断言 REUSED、其他会话、CREATE_INTENT/UNCERTAIN 均不在候选集合。
- [x] 写 test_shared_mapping_retains_active_consumer、test_keep_is_not_delete、test_duplicate_operation_does_not_duplicate_resource；断言创建仅一个、共享引用保留、KEEP 后无清理资格。
- [x] 运行 `python -m pytest backend/tests/test_service_port_ledger.py -q`，确认 RED。
- [x] 实现版本 1 事件重放，沿用唯一幂等键 `{operation_id}:{event_type}`，事件追加不改已有记录；资源索引含 session_id 与 mapping_key，不只使用 ID。
- [x] 运行账本及 test_skill_execution_repository.py，全部 PASS；无模型/迁移改动。
- [x] 已按用户后续指令提交 `feat(skill-execution): track service port ownership events`（79a1231e932a383168beace807e3abe56de41bbf），未推送或合并。

Task 2 验证：相关 60 passed，完整后端 727 passed（332.39s，2026-10-14）；提交后完成门禁再次 60 passed（13.16s）。纯函数账本未接入设备写入流程，不把候选集合当作删除授权；范围裁定和验证见 docs/LOCAL_RUNNER_LIVE_ACCEPTANCE.md。

### Task 3：新计划与已有注册安全分支

**Files:** 修改 coordinator.py、service.py、configuration.py、runtime.py、onu_registration_dual_wan.py；新增 backend/tests/test_service_port_plan.py。
**Interfaces:** build_service_port_plan(parameters:dict, profile:ServicePortProfile|None) -> dict（version=2、steps）；旧 build_plan 和旧计划快照不重写。新动作 verify_existing_registration、inspect_service_mapping、create_service_port、verify_service_port；消费者 IPOE/PPPOE。Profile/GEM 必须先由只读查询确认，Profile 编号不等于 GEM。

- [x] 写 test_v2_reuses_registration_without_delete_or_register，断言不含 FREE_ID/DELETE_EXISTING/REGISTER；身份/Profile 不匹配断言 BLOCKED 且写命令数 0。
- [x] 写 test_old_plan_snapshot_is_unchanged；test_required_restore_blocks_before_any_write；test_shared_mapping_does_not_delete_for_wan_switch，断言保留人工隔离节点。
- [x] 运行 `python -m pytest backend/tests/test_service_port_plan.py -q`，确认 RED。
- [x] 创建时由冻结绑定选择新计划，不接受请求覆盖映射；VLAN 与既有 IPOE/PPPOE 参数必须相符，否则拒绝。旧绑定/旧计划没有新参数时不进入创建流程，不补默认 GEM/ID。
- [x] 新计划在任何配置写入前检查 end_policy：要求完整 RESTORE 时 BLOCKED；KEEP 不绕过逐动作审批。现有恢复保护保持不变，注册缺失不自动转换为重注册。
- [x] 运行计划与 test_skill_coordinator.py、test_local_runner_binding.py、test_local_runner_runtime.py，相关 60 passed；复查历史快照无变更。
- [x] 已按用户后续指令提交 `feat(skill-execution): add safe retained registration plan`（7b5c2e64ad816528e10a5e764744399e84d173f0），未推送/合并。

Task 3（2026-10-14）：相关 60 passed，完整后端 752 passed（370.00s），提交后门禁再次 60 passed（37.45s）。本阶段只接入只读注册/Profile/GEM 核验，通道节点交由 Task 4 实现。configuration.py 沿用 Task 1 字段；Catalog 定义和旧 build_plan 不变。详见 docs/LOCAL_RUNNER_LIVE_ACCEPTANCE.md。

### Task 4：复用、创建与事务边界

**Files:** 新增 service_port_lifecycle.py、backend/tests/test_service_port_creation.py；修改 actions.py、runtime.py、coordinator.py、service_port_contracts.py；repository.py 复用现有追加事件接口，无需修改。契约文件补齐本任务依赖的 PortOperation/PortPreview，含显式目标与消费者。
**Interfaces:** lifecycle.inspect(session_id:str, mapping:ServicePortMapping) -> PortRead；lifecycle.preview(operation:PortOperation, read:PortRead) -> PortPreview；lifecycle.execute_approved(operation:PortOperation, preview_hash:str) -> ActionOutcome。Runner inspect_service_mapping(context)/create_service_port(context) -> ActionOutcome；只调用 allowlist，不直接写事件。

- [x] 写复用、重复匹配、Profile/GEM 缺失反例（部分采用参数化用例），断言完整匹配才 REUSED。
- [x] 写全局 ID 占用、审批漂移、完整操作 hash 及显式 SN/Profile/消费者预览反例，旧 hash 无法批准新范围。
- [x] 写意图先提交测试，文件型 SQLite 的独立 Session 读取已提交 INTENT；提交失败断言 executor 未调用。
- [x] 运行创建测试，确认有效 RED（缺失模块断言从夹具移到测试体后为 13 failed）。
- [x] 实现只读核验 → 审批 → 即时重查 → 意图短事务提交 → 命令 → 后验/Evidence → 结果短事务；显式命令确认和完整一致后验同时成立才 VERIFIED，前后证据均重验。
- [x] 写并运行超时、后验不符、证据失败、结果提交失败、取消及前验证据篡改反例；保留意图/不确定记录，不自动重试。
- [x] 创建、审批、Runner、契约、账本和计划相关 151 passed（58.32s）；最终完整后端 774 passed（348.58s）。预览/事件不含凭据。
- [x] 已按后续用户指令提交 `feat(local-runner): create approved service ports safely`（a3830fa4d8eae6da628655c994f4bf5132d1246f），未推送或合并。

Task 4 限制：仅接受当前支持的完整映射及显式成功回执；陌生回执、不完整读取和同 VLAN 冲突均不判成功。离线通过不是现场创建授权，清理/恢复仍为 Tasks 5–6。详见 docs/LOCAL_RUNNER_LIVE_ACCEPTANCE.md。

### Task 5：逐条清理与共享保留

**Files:** 修改 backend/app/skill_execution/service_port_lifecycle.py、backend/app/local_runner/ma5800/actions.py、backend/app/skill_execution/coordinator.py、backend/app/local_runner/runtime.py、backend/app/local_runner/ma5800/service_port_contracts.py；新增 backend/tests/test_service_port_cleanup.py。Runner 增加全局 ID 资源级只读核验和持久化删除审批守卫；契约修正 DELETE 预览动作标签，CREATE 预览保持不变。
**Interfaces:** lifecycle.preview_cleanup(session_id:str, retained_consumers:frozenset[str]) -> tuple[PortPreview,...]；lifecycle.cleanup(session_id:str, previews:tuple[PortPreview,...], approval_hash:str) -> ActionOutcome。remove_test_services 不从测试前 affected_service_ports 直接得到删除授权；每条单独意图、查询与证据，批次审批 hash 覆盖有序完整集合。

- [x] 写 test_reused_and_cross_session_ports_are_never_deleted、test_shared_active_port_is_retained、test_all_created_ports_are_processed；额外验证外部会话审批不能获取归属。
- [x] 写 test_second_delete_failure_keeps_partial_outcomes；当前双 WAN 最多两条合法映射，验证第二条失败和第一条失败后剩余项 NOT_PROCESSED，不伪造第三条资源。
- [x] 写 test_mapping_drift_or_id_reuse_stops_cleanup、test_already_absent_records_observation_without_delete、test_keep_retains_all_created_ports；包含审批篡改、数据库提交失败、证据损坏、取消和幂等反例。
- [x] 清理核心 RED 15 failed；Runner/KEEP 接入 RED 3 failed；继续实施前 Runner 再次 RED 2 failed；DELETE 标签 RED 1 failed。仅使用脱敏离线设备替身。
- [x] 实现逐条核验与 DELETE_INTENT/DELETE_VERIFIED/UNCERTAIN；空清理集合不发生 I/O。未知/旧账本不得用快照已有端口替代，本次创建与原有资源分离；KEEP 追加 PORT_RETAINED。
- [x] 清理、创建、账本、MA5800 动作、审批、Runner、契约、计划及 Coordinator 相关 204 passed（99.90s）；不自动补建删除资源、不删除 ONT。
- [x] 已按用户后续指令提交 `fix(local-runner): clean only verified session service ports`（6c53c9f945d6ea45ec86723b41f1c2e8a1ca66ba）。完整后端 800 passed，提交前相关 204 passed，提交后阶段门禁 102 passed；未推送、合并或现场执行。

### Task 6：中断恢复与只读详情

**Files:** 修改 coordinator.py、service.py、schemas.py、router.py、service_port_lifecycle.py；新增 backend/tests/test_service_port_recovery.py、test_service_port_lifecycle_api.py。生命周期接口补齐本地意图中断标记及显式只读核对，不放宽既有写入状态保护。
**Interfaces:** lifecycle.reconcile_interrupted(session_id:str) -> tuple[PortResource,...]，只读、不返回自动写入授权；ExecutionRead.service_port_resources 为新增只读列表，含来源、状态、消费者、证据引用，不含凭据。

- [x] 写 test_restart_after_create_intent_never_reissues_command、test_matching_resource_without_verified_event_is_not_owned；断言 RECOVERY_REQUIRED、无自动清理资格。
- [x] 写 test_restart_after_delete_reads_before_new_approval；缺失只记核对事实，存在仍不确定，均不自动写入、不自动解除人工恢复。
- [x] 写 API 测试：请求篡改 owned/端口列表被拒绝；详情来自当前会话事件；旧会话返回空摘要；重复 advance/respond 无重复 I/O；最新核对状态及证据可追溯。
- [x] 修正测试夹具导入后，真实 RED 13 failed（16.64s）；保护历史反例 RED 3 failed；核对摘要反例 RED 1 failed。
- [x] 在现有 recover_interrupted 接入意图核对/状态标记，不在应用启动时主动 SSH；后续明确只读恢复动作才读取设备。复用原 RecoveryTask，不引入自动认领或自动重试接口。
- [x] 恢复/API/账本、既有执行 API/Coordinator 及创建/清理兼容测试 154 passed（121.11s）；完整后端 817 passed（397.04s），详见验收记录。
- [ ] 提交建议 `feat(skill-execution): expose service port recovery state`，等待用户指令。

### Task 7：兼容回归、审核与现场验收交接

集成审核需专项核验完整 PortPreview 到 Router `_pending` / 真实前端的字段投影，尤其 `fsp` / `target_fsp`、Profile、VLAN/GEM、候选 ID 与消费者。只读资源摘要不能代替完整人工审批展示；未验证前不通过现场写入门禁。

**Files:** 新增 backend/tests/test_service_port_lifecycle_acceptance.py；更新 docs/LOCAL_RUNNER_LIVE_ACCEPTANCE.md 和现有非敏感配置说明。2026-10-14 用户批准最小范围调整：修正 Router/Schema 的完整审批字段投影，在现有 TestExecutionPage 内接入 LocalExecutionApproval 组件及测试，不新增导航模块、会话创建或测试功能。
**Interfaces:** 真实 Service → Coordinator → 注入离线 Runner → EvidenceStorage → 事件/API；复用现有 Report/Archive API，仅测试兼容性。

Task 7 本轮记录（2026-10-14）：最小审批接入及审核发现的 ID 漂移/取消恢复问题已修复；最终后端 828 passed，前端 61 passed，生产构建 PASS，diff 检查通过。必要修改另含既有 Vite 同源代理和独立 Node 代理测试。整体审核无 Critical/Minor，两项 Important 已 RED→GREEN 修复；第三项 Important（安全清理核心无正常平台入口）仍需用户范围决策，完整门禁 HOLD。未提交，不标 Task 7 complete；详细文件/证据见 LOCAL_RUNNER_LIVE_ACCEPTANCE.md。

后续用户已批准并确认安全清理入口设计（spec 第 11 节）；本段以上保留原时点状态。新增小型 service_port_cleanup_flow.py 和实际 API/Runner 接线测试；仅 END_POLICY 待确认或人工恢复的 DRAFT/v2 会话可预览/审批，结束后仍需人工恢复，不放宽原执行状态或重写历史计划。沿用现有本地请求串行锁/同源校验与受保护删除 Runner。旧任务不重做，不自动提交、推送或设备验收。

最终软件验收（2026-10-15）：入口真实接线通过；新入口独立审核的终态复活 Important 已 RED→GREEN 修复；后端 846 passed（480.91s），前端 62 passed（84.74s），构建 exit 0，diff 检查通过，无未处理 Critical/Important 或延期 Minor。软件门禁 PASS，18 个文件待用户审核提交。完整 WAN 恢复及现场写入验收不在此 PASS 内；提交前不记录 Task 7 complete 或清理工作区。

- [ ] 先写集成反例：旧 Run/Snapshot/Report hash 不变、新结果不自动 LOCK、共享映射不产生两次创建、超时不产生错误 PASS。
- [ ] 运行该测试确认反例有效，再补齐最少集成接线；成功结果仍由既有人工 LOCK/报告规则约束。
- [ ] 后端：`python -m pytest backend/tests -q -p no:cacheprovider`，全部通过；设置 PYTHONDONTWRITEBYTECODE=1 和独立 basetemp，不使用现场数据库。
- [ ] 前端目录：`npm.cmd test -- --reporter=dot --maxWorkers=1`、`npm.cmd run build`，退出码均 0。
- [ ] 执行 `git diff --check`、`git status --short`，检查仅计划范围，无数据库、Evidence、ZIP、缓存、node_modules/dist、凭据或临时文件。
- [ ] 完成独立整体审核与反例复核；记录实际测试数、错误及未通过项，不把上一轮 603 当成本轮结果。
- [ ] 提交前等待用户确认；此后再另行请求具体只读/写入验收授权。现场首先复用已有映射验证，创建/清理采用明确可恢复的测试资源；完整恢复仍 HOLD，不据离线通过宣称平台全闭环完成。

## 自审与执行出口

设计 1–3 对应 Task 1/3，事件模型对应 Task 2，创建与事务对应 Task 4，清理/KEEP 对应 Task 5，中断对应 Task 6，历史与验收对应 Task 7。五项 Review Focus 均有具名反例。
本计划不执行测试、设备操作或迁移；Task 1 缺可信协议样本时停止该能力，而非猜命令或降低解析门禁。
请用户审核计划并选择：本会话逐任务实施，或子代理逐任务实施。推荐本会话实施加最终独立审核：各任务紧密共享配置、事件和审批契约，可减少交接成本，设备安全风险仍由离线反例及最终独立复核控制。
