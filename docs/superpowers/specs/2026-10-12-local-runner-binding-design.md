# 本机 Runner 目标与凭据接入设计

日期：2026-10-12；代码基线：8b1bc92386cf9833cbc0daa57c3917d089905a84。
状态：方案 A 已选择，本文等待书面设计审核；尚未进入实现。

## 1. 目标与范围

让 Task 9 的执行 API 调用已有 MA5800、ONU Web 和 PC Probe 适配器，形成本机执行、标准事实、Evidence 的闭环。无需 Codex 逐步操控设备，但设备配置变更继续要求操作员明确审批。

用户选择：本机非敏感配置文件加 Windows 系统凭据存储，支持换电脑。不增加数据库表、业务模块或测试范围；保持 DEVELOPMENT、单进程、仅 loopback 访问。不开发 Task 10 前端，不合并或推送，不将设计批准视为现场操作授权。

当前事实：已有 CredentialResolver/keyring、动作注册表、MA5800SSHConnector、NeutralONUWebAdapter、PCProbe，以及可信 Runtime 注入点。默认 Runtime 未配置；真实目标解析、成对凭据映射、标准事实组合仍未接通。完整 WAN 自动恢复能力未经证明，不宣称自动恢复完成。

## 2. 配置文件与迁移电脑

增加设置 local_runner_config_path，默认空。只有显式配置路径并通过校验才创建 Runtime。配置采用 UTF-8 JSON，schema_version=1，extra 字段禁止；初始化只读取配置，不连接设备。

实际配置放在本机 data/local-runner/config.json，排除 Git 和发布包；仓库仅提供无现场信息的配置示例及说明。不保存账号、密码、Cookie、命令或原始输出。文件字段白名单如下：

| 分组 | 字段与约束 |
|---|---|
| 根 | schema_version、enabled、targets、access_bindings |
| OLT 目标 | 目标引用键；kind=MA5800；host 为明确的私网单播 IP；port 为 1–65535；已人工确认的 SSH SHA256 指纹 |
| ONU 目标 | 目标引用键；kind=ONU_WEB；url 为 http/https 私网 IP，无 URL 用户信息；adapter_key=neutral-v1；pc_interface_name 为明确网卡名 |
| 访问映射 | 访问引用键；kind=OLT/ONU_WEB/PPPOE；username_ref、password_ref，均符合已有引用格式且不同 |

拒绝公网、回环、未指定和组播设备目标，不允许从 HTTP 请求传入任意地址、命令或适配器类。已有 Environment 保存 olt_target_ref/onu_web_target_ref 和三组 access_ref；F/S/P、ONT ID、Profile、VLAN、SN、Ping 目标仍来自既有 Device/Environment/执行参数，不在文件中维护第二份。

换电脑：迁移经审核的非敏感配置；重新选择网卡并重新录入六个凭据值；人工复核 OLT 指纹。系统凭据不随 Git、数据库、Archive 或配置一起迁移。绑定数据含现场地址及引用，备份按敏感实验室资料保管。

## 3. 成对凭据与安全边界

一个逻辑访问引用映射到两个已有 keyring 条目。例如某 OLT 访问引用对应 username_ref 和 password_ref，而不是将访问引用本身当作密码。

Runtime.available(access_ref) 检查映射类型和两条凭据均存在；调用方按 OLT/ONU/PPPoE 参数位置再次检查类型。CredentialResolver 及已有凭据 API 仍对单条引用工作，不改变其语义。首次配置通过本机交互式配置工具分别隐藏输入账号和密码，调用已有 Resolver.enroll；不使用命令行参数、配置明文或聊天记录中的旧密码自动入库。该工具仅用于本机配置，不提供设备执行或新远端 API。

Runtime.secrets_for(parameters, action) 只读取本动作需要的凭据，以 SecretValue 传递：OLT 连接账号密码、onu_web_username/password、pppoe_username/password。执行结束关闭 SSH/浏览器资源，不缓存凭据、不输出 repr 之外的原值。任何账号密码都不进入事件、Snapshot、报告、错误消息或 Git。

OLT 登录前核对实际服务器公钥与固定指纹；包括系统 known_hosts 已包含该主机的路径，不能只依赖 MissingHostKeyPolicy。指纹变化必须停止，不自动信任或替换。读取指纹的现场步骤需另行授权。

## 4. 会话绑定与历史不漂移

创建执行时，先合并并校验现有 Environment/请求参数，随后解析配置中的目标和访问映射；任何引用缺失、类型错误或配置非法都在设备动作前拒绝。绑定与创建 Run/Result/Session 同事务完成。

在已有 ExecutionSession.plugin_snapshot 中增加 runtime_binding 子对象，版本 1：固定目标引用、OLT 地址/端口/指纹、ONU URL/适配器/网卡、三组 username_ref/password_ref、配置白名单的 SHA256。仅存引用，绝不存凭据值。该对象创建后不可修改，不改既有 Device、Case、Environment、parameter_snapshot 或 standard_snapshot 内容，不需要迁移。

执行按 session_id 从持久化绑定构造适配器，不重新解析可变配置文件，不接受请求覆盖绑定。凭据值可在系统存储中轮换，但旧会话的条目引用不能重映射；读取失败则阻塞。修改配置只影响新会话；变更须重启本机应用，不做热加载。

旧会话没有 runtime_binding：允许查看及下载，不允许真实执行或自动补写绑定，返回 409 RUNTIME_BINDING_REQUIRED，要求新建 Run。中断会话按既有规则标记恢复；启动不自动恢复现场配置。

PC 地址随 DHCP 变化：每次 PC 动作只从绑定网卡的实时有效地址中选择 ONU 所在网络的唯一候选，记录网卡/源地址/采集时间，不使用默认网卡。缺失、多候选或地址变化导致不确定时进入 WAITING_OPERATOR；不偷偷改绑定、切路由或重试配置动作。

## 5. Runtime 接线与结果生成

配置加载器负责校验及不可变数据；访问解析器负责成对引用；Runtime 负责资源生命周期和白名单动作分派；事实转换器负责将解析数据转成现有标准事实。Router 不构造命令，Coordinator 仍拥有状态、审批、恢复和最终判定。

仅注册现有动作及计划中的 ONU Web/PC 步骤。每个动作按实际会话绑定建立资源并在 finally 关闭。拒绝未知动作，不接受自由脚本。操作超时有界；连接重试不得导致注册、删除、WAN 下发或恢复重复执行。

| 标准事实 | 必需的本次执行来源 |
|---|---|
| olt.autofind.matched | 已解析 autofind 记录的完整 SN、F/S/P 与目标一致；已注册设备不能伪造 autofind 记录 |
| olt.registration.ready | 按 SN 查询后的身份、位置、ONT ID、Profile 及 online/match 满足已固定基线；缺字段不得 PASS |
| ipoe/pppoe.address.valid | 同一 WAN、VLAN 的 OLT 与 ONU Web 状态及有效单播地址相互一致；不能取另一 WAN 的地址 |
| ipoe/pppoe.internet.pass | 对应 WAN 的 ONU Ping 与绑定网卡的 PC 探测均符合已有标准，且当前链路可归属该 WAN |

所有转换使用解析后的结构化数据，数字字符串须显式转为有限数值；不将 ActionOutcome.status=PASS 直接当作标准 PASS。阈值只来自已固定标准，不新增默认 RTT、光功率、DNS 等判定要求。若现有源不能证明 WAN 隔离或探测归属，该事实缺失并 BLOCKED；不能用系统默认 DNS、另一网卡成功或通用 PCProbe.status 替代证明。

每个步骤保留来源和采集时间，E1–E6 继续按固定证据规则保存。OLT 文本渲染 PNG，Web 截图和 PC 证据先脱敏再交给现有存储/hash 校验。证据不齐仍 BLOCKED。已注册目标、无法恢复的配置和缺失事实如实记录，不绕过既有标准以追求 PASS。

## 6. API、审批与失败处理

不增加业务 API，不改变 Task 9 请求字段。配置内容通过本机初始化工具管理，不通过浏览器提交设备地址。已有创建接口对不可用绑定返回 422，避免创建不可执行的新会话；已有旧会话 advance/respond 缺少绑定返回 409。绑定信息和内部引用不加入公共响应。

设备动作后的认证、指纹、页面不兼容、源网卡不可用等异常转换为既有 BLOCKED/ERROR 或 WAITING_OPERATOR，保存安全错误码和可取得的证据，不回显底层连接异常/密码。真实测试 FAIL 不能伪装成环境阻塞。配置路径已显式启用但文件非法时启动失败，不静默退回另一台设备。

设备变更维持精确 preview_hash、明确 approved=true、目标与影响列表确认。注册前再次核对 SN 和空闲 ONT ID；不根据旧聊天信息猜测现场。Run/Result 不自动 LOCK。RESTORE 仅在完整恢复可验证时成功，否则 MANUAL_REQUIRED，禁止扩大恢复承诺。

## 7. 测试与验收

采用 TDD，不在离线测试中访问真实设备。边界替身仅替换 SSH、浏览器、凭据存储和网卡/网络 I/O；Runtime、Service、Coordinator、SQLite 及证据完整性走真实实现。

必须覆盖：严格配置校验；默认禁用；每种访问映射的成对缺失/错类型；公钥变化及 known_hosts 路径；未知目标/动作；快照绑定在配置修改、重启后保持原值；旧会话缺绑定；DHCP 地址缺失/多候选；网络资源关闭及超时；批准前零配置变更；批准哈希不符；标准事实类型/跨 WAN 混用；脱敏及 Evidence hash；重启不自动重放变更。无数据库迁移，已有后端及前端完整回归不得退化。

离线通过后再请求真实现场验收授权：重新确认 DUT 型号/版本/SN、OLT 地址和指纹、F/S/P/ONT ID、Profile/VLAN、ONU 网卡与账号录入。先只读检查，再逐项审批配置变更；创建新 Run，保留旧 Run，验证 O5/online、双 WAN、PC 路径、E1–E6 及手工恢复责任。

本机真实 Runner 接入成功的标准：平台 API 调用到真实适配器，事件、事实、Evidence 可追溯，异常安全阻塞，现场结果不依赖 Codex 代操作。产品正式发布、Task 10 UI 和完整自动恢复不包含在此验收声明中。

## 8. 预期改动与阶段门禁

实现预计新增 local_runner 配置/绑定/Runtime/事实转换模块与测试、本机配置工具及无现场值示例；少量接入 core/config、main、skill_execution 创建流程。复用现有适配器，仅在接线所必需的指纹验证或资源边界上做受测试保护的修正，不重构 Sprint 1–10。

本文审核通过后编写实施计划并选择执行方式，之后才开始 TDD。当前只新增本设计文档；不执行迁移、不修改业务代码、不连接设备、不开始前端。
