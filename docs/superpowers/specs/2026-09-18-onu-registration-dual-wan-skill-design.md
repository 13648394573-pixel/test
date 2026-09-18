# ONU 注册与双 WAN 联网验证 Skill 设计

## 1. 文档状态

- 设计日期：2026-09-18
- Skill 名称：ONU 注册与双 WAN 联网验证
- Skill Code：`ONU_REGISTRATION_DUAL_WAN_CONNECTIVITY`
- 目标版本：`1.0.0`
- 当前状态：设计已确认，实际标准保持 DRAFT，等待实验室验证
- 首版 OLT：华为 MA5800-X7
- 执行形态：单机、本地、受控半自动

本文定义 ONU Test Workbench 的第一个真实 Test Skill。它只覆盖 ONU 注册、OLT 下发 IPoE/PPPoE WAN、获取地址和上网 Ping 验证，不包含 VLAN 端口绑定、QoS、IPv6、其他 OLT、AI 判断、云端服务或无人确认的破坏性操作。

## 2. 目标与成功条件

本 Skill 用于回答四个问题：

1. OLT 是否能自动发现并正确上报目标 ONU 信息？
2. ONU 是否能使用指定模板成功注册并进入 `online/O5/match`？
3. IPoE 和 PPPoE 是否能按选择的模式成功下发并获取有效地址？
4. IPoE 和 PPPoE 是否能作为实际承载通道分别完成上网 Ping 验证？

执行成功必须形成可复核的标准证据链：测试标准版本、输入参数、执行步骤、结构化观察值、六组核心截图、原始日志、操作人员确认和最终结论相互关联，且文件具有 SHA256 校验值。

## 3. 设计原则

- 一个 Skill 对应一个完整业务能力，内部步骤可以复用受控 Runner Action。
- 默认采用严格标准；客户/地区标准只能通过版本化 Standard Profile 明确调整。
- 查询动作可以自动执行；删除、清理、切换承载和恢复等高影响动作必须弹窗确认。
- 数据库只保存 Runner Plugin/Action 标识和凭据引用，不保存任意命令正文或明文秘密。
- 原始 OLT 文本是解析和判断依据，渲染后的 PNG 是报告证据。
- ONU Web 页面同时保存截图和可解析文本；截图本身不作为唯一机器判断来源。
- 功能失败与环境阻塞分开：设备不满足标准为 FAIL，环境或必要证据不可用为 BLOCKED。
- 未完成真实 PASS、FAIL、BLOCKED 三类验证前，Skill 和标准不得发布。

## 4. 适用范围

### 4.1 适用设备

- 支持 GPON/XPON 接入且能够被 MA5800-X7 自动发现的 ONU/光猫。
- 支持通过 OMCI 下发 IPoE/DHCP 和 PPPoE WAN。
- 提供可访问的 ONU Web WAN 状态页和诊断 Ping 页面，或由产品适配器提供等价数据与截图能力。

### 4.2 首版环境

- OLT：Huawei MA5800-X7，通过 SSH 连接。
- ONU Web：默认本地管理地址由环境模板提供。
- 测试电脑：Windows，本地运行 Workbench 与 Runner，可通过 ONU LAN 或 Wi-Fi 进行用户侧联网验证。
- OLT、ONU、PPPoE 凭据：使用 Windows 本机凭据引用，报告中不出现明文。

### 4.3 非目标

- 不同时适配其他品牌 OLT。
- 不允许用户输入任意 OLT 命令并由系统执行。
- 不自动删除生产配置或绕过人工确认。
- 不依赖云端、在线 API 或运行时下载。
- 不在本 Skill 中加入 TR069 专项、光功率门限、吞吐量、VLAN 端口绑定、QoS 或 IPv6 测试。

## 5. 输入参数

参数由 Environment Template、Standard Profile、Device Profile 和当前执行表单合并。执行前显示最终值并要求确认。

| 参数组 | 关键参数 | 规则 |
|---|---|---|
| OLT | 主机、端口、凭据引用、frame、slot、PON port | 环境模板必填 |
| 注册 | ONU SN、认证方式、line profile、service profile、ONT ID 策略 | SN 必须与自动发现结果一致；ONT ID 默认自动选择空闲值 |
| WAN | VLAN、priority、GEM port、IP host index | 客户/环境模板提供；IPoE 和 PPPoE 不得错误复用同一 host index |
| PPPoE | 用户名/密码凭据引用 | 数据库和报告不得保存明文 |
| 执行模式 | `SEQUENTIAL_ISOLATED` 或 `CONCURRENT_DUAL_WAN` | 启动时弹窗选择并写入执行快照 |
| 双 WAN 判定 | `STRICT_PER_WAN` 或 `CUSTOMER_SIMPLIFIED` | 默认为严格模式；简化模式必须由客户标准允许 |
| 网络目标 | 公网 IP、域名、Ping 次数、丢包率和时延阈值 | 按客户/地区标准带出，执行前可修改并记录 |
| ONU Web | 管理地址、凭据引用、产品页面适配器 | 页面路径不得硬编码到 Skill 规则中 |
| 结束策略 | `RESTORE` 或 `KEEP` | 结束时弹窗选择，默认恢复 |

当前实验室已验证过的 F/S/P `0/2/10`、line profile `10`、service profile `10`、VLAN `1000` 只作为可编辑的本地环境模板示例，不属于 Skill 的固定规则。

## 6. 执行流程

### 6.1 预检与快照

1. 加载 Skill、Standard Profile、环境、设备和 Runner 版本。
2. 验证必填参数和凭据引用存在，不读取或记录秘密明文。
3. 检查 OLT SSH、ONU Web 和测试电脑网络接口可达性。
4. 读取并保存测试前 ONU 注册、WAN 和 service-port 状态快照。
5. 建立执行会话、事件时间线和证据目录。

### 6.2 ONU 自动发现与注册

1. 执行 `display ont autofind all` 等受控查询动作。
2. 从输出提取 SN、F/S/P、Vendor ID 和发现状态。
3. 生成“OLT 上报 ONU 信息”原始文本和渲染截图。
4. 若同一 SN 已注册，显示 F/S/P、ONT ID、SN 和影响范围。
5. 工作人员确认后才可删除旧注册；取消则进入 BLOCKED。
6. 查询目标 PON 口已用 ONT ID，并选择空闲 ID。
7. 使用配置参数注册 ONU。
8. 轮询注册状态，直到达到 `online/O5/match` 或超时。
9. 生成“注册成功”原始文本、结构化观察值和渲染截图。

### 6.3 顺序隔离模式

默认模式为 `SEQUENTIAL_ISOLATED`：

1. 只下发 IPoE WAN。
2. 等待 IPoE 获取地址，采集 OLT WAN 信息和 ONU Web WAN 页面。
3. 确认实际流量使用 IPoE，执行 ONU Ping 与电脑侧联网检测。
4. 保存 IPoE 地址与 Ping 核心证据。
5. 弹窗确认后清理或禁用 IPoE 测试配置。
6. 只下发 PPPoE WAN。
7. 等待 PPPoE认证和取址，采集 OLT/ONU 双侧信息。
8. 确认实际流量使用 PPPoE，执行 ONU Ping 与电脑侧联网检测。
9. 保存 PPPoE 地址与 Ping 核心证据。

顺序隔离模式用于最强地证明两类 WAN 都能独立承担实际流量。

### 6.4 双 WAN 同时下发模式

`CONCURRENT_DUAL_WAN` 用于客户要求 IPoE 与 PPPoE 共存的场景：

1. 使用不同 IP host index 下发两条 WAN。
2. 采集两条 WAN 同时存在、均已取址的 OLT 和 ONU Web 证据。
3. `STRICT_PER_WAN`：弹窗指导工作人员依次切换默认承载；每次切换后重新采集 WAN 状态、ONU Ping 和电脑侧联网结果。
4. `CUSTOMER_SIMPLIFIED`：仅当客户标准明确允许时，两条 WAN 都取址后执行一次整体联网验证。
5. 简化模式报告必须标注“未分别切换承载通道验证”，不得描述为两条 WAN 分别通过上网测试。

### 6.5 结束与恢复

1. 汇总功能结论和证据完整性。
2. 弹窗选择恢复测试前状态或保留当前配置，默认恢复。
3. 删除注册、WAN、service-port 或切换配置前再次展示影响范围并确认。
4. 执行恢复后重新查询 OLT/ONU 状态，验证恢复成功。
5. 恢复失败时创建 Recovery Task，保留明确的人工处理指引，不伪造完成状态。
6. 生成本地 JSON/HTML 报告和证据清单。

## 7. 六组核心证据

六组是报告逻辑分组，不等于只有六个文件。地址组必须同时含 OLT 与 ONU Web 截图；Ping 组包含 ONU 诊断和电脑侧验证证据。

| 证据组 | 必要内容 | 主要来源 |
|---|---|---|
| E1 OLT 上报 ONU 信息 | SN、F/S/P、Vendor ID、发现状态 | autofind 原始文本 + 终端 PNG |
| E2 注册成功 | ONT ID、SN、online、O5、match、line/service profile | ONT info 原始文本 + 终端 PNG |
| E3 IPoE 获取地址 | Connected/Up、IP、掩码、网关、DNS、VLAN | OLT wan-info PNG + ONU Web WAN PNG |
| E4 IPoE Ping | 目标、承载 WAN、收发包、丢包率、时延 | ONU Ping PNG + 电脑侧结果 PNG/结构化记录 |
| E5 PPPoE 获取地址 | Connected/Up、IP、掩码、网关、DNS、VLAN，秘密已遮盖 | OLT wan-info PNG + ONU Web WAN PNG |
| E6 PPPoE Ping | 目标、承载 WAN、收发包、丢包率、时延 | ONU Ping PNG + 电脑侧结果 PNG/结构化记录 |

每个证据文件记录：执行 ID、Skill/步骤、标准条款、采集时间、采集方式、原始路径、SHA256、脱敏状态以及用于判定的字段和值。

无法自动截图时，系统弹窗说明需要打开的页面和必须包含的字段，允许工作人员重试或手工上传。功能观察正常但强制证据不完整时，不允许形成完整 PASS；功能结论可保留，执行完整性标记为 INCOMPLETE/BLOCKED。

## 8. 默认判定规则

以下规则属于待实验室校准的 DRAFT 默认值。

### 8.1 注册 PASS

- 自动发现结果包含目标 SN，且 F/S/P 与执行参数一致。
- 注册命令成功，ONT ID 有效。
- 在标准超时内达到 `online`、`O5`、`match`。
- line profile 与 service profile 符合执行快照。
- E1、E2 证据完整。

### 8.2 IPoE PASS

- OLT 和 ONU Web 均识别到目标 IPoE WAN。
- 状态为 Connected/Up。
- IP 非空且不是 `0.0.0.0`；网关、DNS、VLAN 符合标准。
- 严格模式下已证明实际承载为 IPoE。
- Ping 满足目标、次数、丢包率和平均时延标准。
- E3、E4 证据完整。

### 8.3 PPPoE PASS

- OLT 和 ONU Web 均识别到目标 PPPoE WAN。
- PPPoE认证成功，状态为 Connected/Up。
- IP 非空且不是 `0.0.0.0`；网关、DNS、VLAN 符合标准。
- 严格模式下已证明实际承载为 PPPoE。
- Ping 满足标准。
- E5、E6 证据完整且账号密码已脱敏。

### 8.4 Ping 默认值

- 默认次数：4。
- 默认丢包率：0%。
- 默认平均时延：小于 100 ms。
- 目标和阈值由客户/地区标准覆盖；不得用在当地不可达的固定网站误判 ONU。
- 公网 IP、DNS 和 HTTP/HTTPS 可作为 Standard Profile 中的补充检查；本 Skill 的主联网证据为 Ping。

### 8.5 总体结论

- PASS：注册、IPoE、PPPoE 和适用的双 WAN 规则全部通过，六组证据完整。
- FAIL：环境已确认正常，ONU 注册、取址或指定 WAN 上网行为不符合标准。
- BLOCKED：OLT/ONU/测试网络/凭据/标准参数/人工确认或必需证据不可用，无法可靠判断设备能力。

典型 FAIL 包括：无法注册、无法进入 O5、WAN 在超时后不取址、指定 WAN Ping 不符合标准、OLT 与 ONU Web 的关键 WAN 数据冲突。典型 BLOCKED 包括：OLT不可达、光纤或供电未确认、PPPoE测试账号不可用、工作人员取消高影响操作、ONU Web 无法采集强制截图。

## 9. 组件与数据映射

### 9.1 Workbench 数据

- `test_skills`：Skill Code、版本、目标、适用设备和 DRAFT/PUBLISHED 状态。
- `skill_parameters`：环境、注册、WAN、模式、目标和结束策略参数。
- `skill_steps`：预检、发现、注册、IPoE、PPPoE、判断和恢复步骤。
- `skill_execution_rules`：步骤顺序、重试、等待、人工确认和恢复入口。
- `skill_evidence_rules`：E1–E6 的类型、必要字段、数量和脱敏要求。
- `skill_standard_bindings`：绑定注册、地址和 Ping 的版本化标准条款。
- `runner_plugins` / `runner_actions`：登记 MA5800、ONU Web、PC Probe 的受控动作。
- `execution_sessions` / `execution_events`：执行状态和追加式事件。
- `operator_interactions`：删除、切换、接线、恢复和保留配置的确认记录。
- `recovery_tasks`：中断或恢复失败后的待处理事项。
- `run_results` / `evidences`：功能结论、完整性结论和证据文件。

### 9.2 Runner 边界

- MA5800 Runner 只公开命名动作，例如 `discover_onts`、`read_ont_state`、`register_ont`、`provision_ipoe`、`provision_pppoe`、`read_wan_state` 和 `restore_snapshot`。
- Skill 不能传入任意命令字符串。
- 高影响 Action 必须声明风险等级、预览影响并等待有效 Operator Interaction。
- ONU Web Adapter 按产品/固件封装页面导航、字段提取和截图位置，避免把页面选择器写入 Skill 标准。
- PC Probe 只进行当前测试网络接口的受控 Ping/DNS/HTTP 检测，不改变系统全局配置，除非有明确人工确认。

## 10. 用户界面

执行向导只服务本 Skill，不扩展为复杂自动化流程：

1. 选择设备、环境和客户/地区标准。
2. 核对 SN、OLT端口、模板、VLAN、凭据引用和网络目标。
3. 选择顺序隔离或双 WAN 同时下发，以及适用的双 WAN 判定规则。
4. 查看步骤时间线、当前状态、结构化观察值和 E1–E6 证据卡片。
5. 在删除、切换承载、人工接线和恢复节点处理弹窗。
6. 结束时选择恢复或保留配置。
7. 查看结论、失败/阻塞原因和本地报告。

## 11. 安全与隐私

- OLT、ONU 和 PPPoE 密码只通过 Windows 本机凭据引用获取。
- 内存中的秘密只用于当次 Action，日志、截图、数据库和报告必须脱敏。
- OLT 原始输出中出现 Password、LOID 或 PPPoE秘密时，持久化前生成脱敏副本；如需保留受限原始文件，必须由独立本机安全策略控制，不进入普通报告。
- 所有证据仅保存在本机；不上传云端。
- 删除注册、WAN、service-port 和恢复操作均需要人工确认并写入审计事件。
- 中断后不假设配置已恢复，必须通过查询验证或创建 Recovery Task。

## 12. 实验室验证与发布门槛

### 12.1 阶段一：只读验证

- 验证 SSH、命令层级、分页/确认提示、文本解析和终端 PNG。
- 执行 autofind、ONT状态和WAN状态查询，不修改配置。

### 12.2 阶段二：受控注册

- 验证已有注册识别、确认弹窗、空闲 ONT ID、注册、O5等待和E1/E2证据。

### 12.3 阶段三：WAN 实测

- 先验证顺序隔离模式的 IPoE 与 PPPoE。
- 再验证双 WAN 共存、严格切换和客户简化规则。
- 对不同 ONU 型号/固件记录页面和 OMCI 行为差异，并通过适配器解决。

### 12.4 阶段四：异常与恢复

- 覆盖 ONU 未发现、ONT ID冲突、注册超时、WAN不取址、PPPoE认证失败、Ping失败、截图失败和执行中断。
- 验证 FAIL 与 BLOCKED 不混淆，验证 RESTORE 和 Recovery Task。

### 12.5 发布条件

至少形成三次正式记录：一次正常 PASS、一次人为制造的功能 FAIL、一次环境 BLOCKED 并成功恢复。命令、超时、页面字段、截图时机和阈值根据实测校准后，才允许将 Skill 和 Standard Profile 发布为 `1.0.0`。

## 13. 实施分期

1. Skill 与标准草案：建立参数、步骤、E1–E6证据规则、标准绑定和本地环境模板。
2. 受控动作：实现 MA5800-X7 只读与变更 Action、ONU Web Adapter、PC Probe、脱敏和截图。
3. 执行编排：实现状态机、确认弹窗、顺序/双 WAN 分支、证据关联、恢复和报告。
4. 真实验证：与测试人员在本地实验室逐步执行并修正。
5. 发布：满足实验室门槛后发布 `1.0.0`，再开始下一个功能 Skill。

## 14. 验收标准

- 安装后的本地 Workbench 能在无互联网下载依赖的情况下启动该 Skill。
- MA5800-X7 查询、注册和 WAN 下发只通过登记的受控 Action 执行。
- 所有高影响动作都有明确弹窗和确认记录。
- 顺序隔离和双 WAN 同时下发两种模式都可选择，实际模式进入执行快照和报告。
- IPoE、PPPoE 能分别形成地址与 Ping 结论。
- E1–E6 六组核心证据完整、可查看、可校验并与标准条款关联。
- 报告不泄露 OLT、ONU 或 PPPoE秘密。
- PASS、FAIL、BLOCKED 和恢复状态可被真实实验室用例稳定复现。
- 本 Skill 验证完成前不并行开发 VLAN、QoS、IPv6 或其他 OLT Skill。
