# Local Runner 现场组件验收记录

日期：2026-10-12（Asia/Shanghai）。分支：codex/skill-execution。
代码基线：189ffed9240b8637fce4c734ce6c41d8bfc25a4c。

## 结论与边界

**本次范围：PASS WITH OBSERVATIONS；完整平台执行闭环：NOT_EXECUTED。**
当前仅证明现有 Python/Playwright/MA5800 组件可在本机对真实设备执行以下检查。
测试由 Codex 调度本机临时命令，使用既有组件和 OS keyring；不是已交付的一键自主运行，
不是通过 Skill Execution API 创建并推进持久化会话的验收。
未创建 TestRun/RunResult，未自动 LOCK，未通过平台生成 Evidence、Report 或 Archive。
旧离线记录 `LOCAL_RUNNER_BINDING_ACCEPTANCE.md` 保留当时结论，不覆盖历史。

用户明确把 LAN 端口绑定、NAT、LAN→WAN 转发及电脑侧真实上网留给另一个功能测试 Skill。
这些项为 SKIP_BY_USER，不是 PASS；现有执行器 PC/WAN 路径归属门禁不因此解除。
本次没有修改业务代码、迁移、数据库、共享 Profile、其他 ONU 或 Git Tag。

## 目标及安全前置

- 实际 OLT 提示符：MA5800-X7。SSH 公钥指纹先只读获取，经用户可信渠道核对后固定。
- 实际 ONU：OLT Equipment ID 为 UN-G711AX；Web 固件 V3.1.20p11、硬件 V1.0。
- 当前 Web SN 与 OLT autofind SN 一致；提交文档仅保留序列号尾号 C999。
- 实际发现位置 0/2/9；不能沿用旧型号、版本或 ONT ID 12。
- Profile 10/10 均为 BT-GPON；Line Profile GEM 1 映射 VLAN 1000。
- 查询发现 ONT ID 0–13、100 已占用；14 空闲。下发前重新检查身份及占用。
- OLT、ONU Web、PPPoE 凭据由用户隐藏输入登记 OS keyring；配置不保存密码且被 Git 忽略。
- 初次 OLT 认证被拒绝，重新登记后认证成功；未连续猜测或爆破密码。
- Codex 浏览器控制工具仍有 Windows 沙箱初始化错误；本地独立 Chromium 可以启动并登录 ONU。

## 注册与 WAN 实测

| 项目 | 实测结果 | 判定 |
|---|---|---|
| 初始注册状态 | autofind 匹配；按 SN 查询明确返回 ONT 不存在 | 前置已核实 |
| 注册 | 0/2/9:14，SN 身份匹配，Profile 10/10 | PASS |
| OLT online / match | online / match | PASS |
| ONU PON | O5 | PASS |
| 光功率 | Rx -13.448616 dBm；Tx 2.339613 dBm | 已采集，不作范围合格判定 |
| Config state / LOID | failed / LOID Error | OBSERVATION，原因未确定 |
| service-port | 新增 288，VLAN 1000 / GEM 1 / ONT 14，up | PASS |
| IPoE | 下发 ip-index 1；OLT、Web 均已连接并获取地址和网关 | PASS（建链） |
| PPPoE | 下发 ip-index 0；初始 Connecting/down，后续两侧均连接并获取地址和网关 | PASS（建链） |

OLT 后续展示 WAN Index 1/2，不能与下发使用的 ip-index 0/1 混同。
Web 实际接口为 IPoE nas0_0、PPPoE ppp0_nas0_1；诊断下拉框为 nas0_0、ppp0。
IPoE 服务类型 INTERNET，PPPoE 服务类型 TR069；建链不代表 ACS 验收。
OLT WAN 字段显示 NAT Disable、DNS 地址为空；仅保留读值，不推断 LAN 转发或 DNS 失败。
两个异常由用户授权保留记录并继续业务验证，不能写成已修复或根因已确认。

## ONU 侧分层 Ping

每轮明确选择对应接口、核验选中值，未使用 Any。两条 WAN 未断开或修改。
每项发送 4 包、收到 4 包、丢包 0%；表中延迟为本次解析的平均值。

| 绑定接口 | 目标 | 平均延迟 ms | 结果 |
|---|---|---:|---|
| IPoE nas0_0 | IPoE 网关 | 1.978 | PASS |
| IPoE nas0_0 | 1.1.1.1 | 50.811 | PASS |
| IPoE nas0_0 | www.baidu.com | 9.275 | PASS |
| PPPoE ppp0 | PPPoE 网关 | 1.786 | PASS |
| PPPoE ppp0 | 1.1.1.1 | 51.240 | PASS |
| PPPoE ppp0 | www.baidu.com | 9.149 | PASS |

这证明 ONU 内置诊断在所选 WAN 上可达上述目标。域名探测成功不替代电脑侧新鲜 DNS 查询，
也不证明 ONU DNS Proxy、LAN NAT、电脑出口归属、HTTP/HTTPS 或所有公网目标可用。

## DHCP 与电脑恢复

目标网卡以太网 4（GUID 核对），临时启用 DHCP/IP/DNS；其他网卡未关闭。
临时设置该网卡 metric 5000，使默认公网路径继续走以太网 2。
实际租约：192.168.1.2/24；DHCP 服务器、网关、DNS 均为 192.168.1.1。
**DHCP 地址及选项交付 PASS；DNS 服务可用性未测试。**

恢复时 metric 与 AutomaticMetric 同时设置返回参数错误；随后分开设置成功。
独立查询确认恢复至：

- 静态 192.168.1.10/24 与 192.168.132.10/24，SkipAsSource=false。
- DHCP Disabled，DNS 列表为空，无 ONU 网卡默认路由。
- InterfaceMetric=25，AutomaticMetric=Enabled。
- 默认公网路由仍为以太网 2，未把控制链路的联网当作 ONU 证据。

DHCP 原始 transcript 位于主工作区已忽略的 `data/local-runner/dhcp-smoke-20261012.txt`。

## 兼容性问题与证据边界

发现：当前固件 Ping 页面无包数控件，固定发送 4 包；调用现有 run_ping(target, 5)
会等待 5 包而超时。原始子帧输出实际为 4/4、0% 丢包。
本轮改用调用参数 4 完成组件验证。后续代码核对确认，正式 BoundExecutionRuntime
在 ONU Ping 分支已经传入 4，并有固定 4 包及旧结果保护的测试。
因此这次超时属于现场临时命令传入 5 的调用不匹配，不是已证实的当前 Runner 缺陷。
不需要把所有固件硬编码为 4，也不应放宽包数校验来接受旧结果；本轮不修改业务代码。
其他调用入口或其他固件的包数协商未在本次现场验证，不据此承诺通用兼容。

除 DHCP transcript 外，身份/OLT/PON/WAN/Ping 的本轮依据为本对话实际工具输出。
没有为这些步骤保存新的独立 PNG、原始文本文件或平台 Evidence Hash；文档是摘要而非原始证据包。
已有用户截图用于前置判断，不冒充配置后截图。未制作虚构附件或补写旧 Run。

## 现场保留与下一步

用户授权 KEEP：目标 ONU 注册、双 WAN 和 service-port 288 保留，未尝试自动恢复 OLT/ONU。
没有执行 OLT save、重启或掉电，不能承诺设备变更的掉电持久性。
电脑临时网络变更已恢复；本轮不再操作设备。

待审核下一步：在平台中新建会话验收持久化动作、交互审批、
脱敏 Evidence 与历史快照/显式 LOCK/Report/Archive 链路。需另行审批，不在本文档任务中实施。
LAN 功能测试留待用户规划的独立 Skill，不在本轮新增或实现。

## 平台持久化接入预检（同日追加）

用户授权重新注册目标 0/2/9:14 后，先使用现有 Alembic Migration 从空库升级至
20260918_0021，并以真实 LocalRuntimeFactory、OS keyring 和现有 Skill Execution API
准备新会话。验收使用独立数据库，不连接旧历史数据库，不使用 metadata.create_all。

结果：**BLOCKED，尚未执行设备动作。** POST /api/skill-executions 返回 409。
同一独立数据库中复现底层错误为 CHECK constraint failed: ck_run_results_result_source。
迁移 20260918_0016 的约束只允许 MANUAL / RULE_ENGINE；现有会话创建写入 LOCAL_RUNNER，
后续迁移没有调整该约束。会话创建事务回滚，未生成新 Run、RunResult 或 ExecutionSession。
创建后才会执行的设备动作未触发；目标注册、WAN、service-port 没有因本次预检被修改。

此前本次定向 API/绑定闭环测试 46 passed（63.74 秒），但使用 ORM 建表的测试数据库，
不能证明真实 Migration 数据库支持该写入。现场辅助脚本和验收数据库位于主工作区
已忽略的 data/local-runner/ 下，不属于提交内容；没有将凭据值写入脚本或文档。

下一步需批准最小兼容性修复：先增加真实迁移数据库的会话创建失败测试，
再用新增迁移调整结果来源约束，保留 MANUAL / RULE_ENGINE 兼容，并执行回归。
不手工改库、不伪装结果来源、不重写历史迁移；修复验证通过前不删除 ONU 注册。

## 已批准的最小兼容修复（同日追加，未提交）

新增 20261012_0022，基于 20260918_0021，仅替换 run_results.result_source
CHECK 约束，允许 MANUAL / RULE_ENGINE / LOCAL_RUNNER；同步 ORM 约束，
避免 metadata 建表与迁移建表的来源范围继续不一致。未知来源仍被拒绝。
未重写旧 Migration、未修改 Service/Router/Runner/Device 逻辑。
已有 LOCAL_RUNNER 结果时明确拒绝降级；无此类结果时可安全恢复旧约束。

测试先行：API 创建在真实 Migration 数据库上先返回 409；旧库升级后写入
LOCAL_RUNNER 先被 CHECK 拒绝（2 failed / 1 passed），再实施修复。
修复后定向 3 passed：真实 API 创建和持久化、旧 LOCKED 结果/快照/Evidence
及已有单条 Evidence 关联保持不变、未知来源拒绝、外键完整性、降级拒绝与无 Runner 结果时降级。
外部凭据使用测试存储替身；没有推进会话、连接或修改现场设备。

完整验证：

- 后端：python -m pytest backend/tests -q -p no:cacheprovider；538 passed（313.05 秒）。
- 前端：npm.cmd test -- --reporter=dot --maxWorkers=1；24 文件、54 passed（76.11 秒）。
- 构建：npm.cmd run build；TypeScript/Vite 通过。
- git diff --check 及新增文件空白检查通过（仅正常 LF/CRLF 提示）。

仅测试数据库执行了新迁移；正式数据库、现场独立验收库尚未升级。
现场门禁保持 BLOCKED/待重新验证，不把自动化测试通过写成真实 ONU 闭环通过。
待代码审核后，先备份并升级独立验收库，再新建平台会话，重新核对目标、
当前注册/WAN/service-port 及每项 preview_hash。ONT ID 如发生变化必须另行确认；
不因用户授权 14 就自动批准其他 ID。LAN/NAT 仍不在本轮范围。

## 独立只读审核（同日追加）

审核结论：本次兼容修复无 Critical / Important 问题，可继续下一阶段。
审核人独立执行新增迁移测试：3 passed（7.53 秒），git diff --check 通过。
完整后端/前端/构建及原 RED 结果为作者执行证据，不冒充审核人重复验证。
一项非阻塞观察：历史种子只包含单条 Evidence 关联，未直接覆盖一个 Evidence
关联多个 Result，也未直接覆盖已有 ExecutionSession/Result 双向引用的升级场景。
前述测试覆盖表述已收窄；不将这些未直接覆盖的场景写成已验收。
现场操作、正式数据库升级及真实 DUT 闭环不属于此次代码审核结论。

## 第一步：独立验收数据库备份与升级（2026-10-13）

日期/时区：2026-10-13，Asia/Shanghai。代码基线：codex/skill-execution，
b2eb172de33faaa5b4992bb4219605feb630777b；执行前工作区干净。
仅处理主工作区 data/local-runner/platform-live-20261012/acceptance.db，
没有启动应用、创建会话、连接 ONU/OLT 或推进配置动作。

先使用 SQLite backup API 创建一致性备份，再验证备份完整性、外键及全部业务表数据。
备份：acceptance-before-0022-20261013-090531-258509.db（与验收库同目录，被 Git 忽略）。
SHA256：eba3db3f454f4ddb41c532df35e7e7c0b7a867af1b74bbead0b955ee30376e50。
备份版本为 20260918_0021，integrity_check=ok，foreign_key_check 无异常。

实际升级：20260918_0021 → 20261012_0022；使用现有 Alembic 迁移，未手工改库。
升级后 integrity_check=ok，foreign_key_check 无异常；43 张业务表的行数及全部行
内容摘要与备份一致（不把 alembic_version 版本变更计作业务数据变化）。
TestRun / RunResult / ExecutionSession / ExecutionEvent 均保持 0。
正式 data/test_workbench.db 升级前后文件 SHA256 相同；没有执行正式库迁移。

第一步结果：PASS。辅助脚本、备份和验收库均仅在已忽略的 data/local-runner/ 下。
仅文档追加属于本轮 Git 变更，未提交或推送。真实平台会话验收尚未开始，
没有解除现场闭环门禁；下一步才创建新会话并核对目标及审批影响范围。

## 第二步：新平台会话与只读现场预检（2026-10-13）

使用已升级的独立验收库，真实 Runtime/凭据/OLT 通过现有 FastAPI Router 创建会话。
调用由本机 TestClient 调度（不是浏览器 UI 一键验收）；没有替换现场 SSH I/O。
POST /api/skill-executions 返回 201，原迁移约束 409 已解除。

- Session：fef38db6-5988-43b1-9a60-3750a3e2df32。
- TestRun：5afd8d6a-5b80-46b9-8ba0-6406dd38d883。
- RunResult：6896b829-e3e3-4e16-8832-f5ab45f8a3e7。
- PREFLIGHT、AUTOFIND 动作 PASS；AUTOFIND 查询成功不等于目标未注册 ONU 已上报。
- SNAPSHOT 动作 BLOCKED；平台当前仍为 RUNNING / DRAFT，未完成或 LOCK。

平台生成并保存 4 份证据，列表及下载全部 200，每份下载内容大小及 SHA256
与元数据一致。数据库现有 Run/Result/Session 各 1；配置变更动作开始事件为 0。
尚无审批交互；没有删除注册、重新注册、WAN 下发、修改 LAN/NAT 或覆盖旧 Run。

脱敏注册文本显示 F/S/P 0/2/9、ONT-ID 14、online / failed / match。
独立只读 Runtime 复核返回 OLT_TARGET_IDENTITY_MISMATCH；这是程序身份比较拒绝，
不是已确认换设备或解析器故障的根因。首次临时复核未提供证据目录，返回泛化 I/O
阻塞，不能据此判断现场网络故障；补齐证据目录后才得到上述具体身份阻塞码。
该复核生成的两份诊断证据位于已忽略目录，未冒充新增平台 Evidence。

结论：平台创建/持久化/证据下载校验 PASS；真实执行闭环仍 HOLD。
先核对 SN/FSP/ONT-ID 的实际值和解析比较差异，不绕过身份门禁，不批准变更。
本轮没有业务代码修改、提交或推送，仅追加验收文档；独立验收库新增真实预检记录。

## 身份阻塞只读根因核对（2026-10-13）

从已有会话冻结参数读取目标，只读执行 display ont info by-sn，比较 OLT 原始
身份字段与现有 parse_ont_state 的输出。F/S/P 均为 0/2/9，ONT-ID 均为 14。
OLT SN 字段格式为「16 位十六进制 SN (厂商 ASCII 显示名)」，十六进制部分与
冻结 SN 完全一致（本文继续只保留尾号 C999，不补写完整序列号）。
现有解析器对整个字段执行 upper()，没有规范化括号内显示名；_same_identity
将整段字符串与纯十六进制 SN 比较，因此返回 OLT_TARGET_IDENTITY_MISMATCH。
本次查明的是解析兼容问题，不是发现目标位置或实际十六进制 SN 改变。

未修改身份校验、数据库快照、Run、设备配置或业务代码。临时诊断首个调用因
导入不存在的命令模块失败，尚未连接设备；改用现有 transport 命令类型后完成查询。
修复建议待批准：TDD 覆盖纯十六进制、已确认的括号显示格式、异常/歧义字段及
真正不匹配的身份；仅规范化 SN 解析，不绕过严格的 SN/FSP/ONT-ID 比较。
修复后保留本次阻塞历史，新会话/后续处置另行决定，不回写旧冻结参数。

## SN 格式最小修复与独立只读复验（2026-10-13）

按批准范围采用 TDD：新增测试先出现 13 failed / 21 passed，复现括号显示名
误拦截及异常/歧义字段被接受；修复后同组测试 34 passed（0.79s）。
完整后端回归 554 passed（320.75s）。仅修改 parse_ont_state 的 SN 解析和测试：
接受 16 位十六进制及一致的厂商显示注释，拒绝重复、矛盾和额外尾随字段。
SN/FSP/ONT-ID 的严格身份比较未修改；未新增功能或执行数据库迁移。

使用已有会话冻结的 RuntimeBinding 和 parameter_snapshot，只读打开独立验收库，
直接调用真实 BoundExecutionRuntime.snapshot_ont；未启动应用、未推进旧会话。
本次不是浏览器一键验收或新平台 Run，证据不冒充新增平台 Evidence。

- SNAPSHOT_STATUS=PASS，error_code=None；规范化 SN 与冻结 SN 一致。
- 位置 0/2/9、ONT-ID 14；online / failed / match。
- WAN 数量 2，当前解析出的 service-port 数量 0；不据此声称 WAN 连通 PASS。
- 本轮两份文本/PNG 证据位于 main 已忽略的 data/local-runner/sn-readonly-recheck-20261013/。
  文件大小和 SHA256 与生成元数据一致。
- 验收数据库文件 SHA256 前后相同，配置写入为 0；历史 Run/Result/快照未改。

首次辅助调用已读取成功，但证据校验误把相对路径当作工作目录路径，退出 1；
只修正被忽略的临时脚本路径后，重复只读复验退出 0，证据校验全部通过。
此辅助脚本错误不是产品解析或设备 I/O 故障。

结论：SN 解析缺陷的软件回归和现场只读复验 PASS；完整真实执行闭环仍 HOLD。
Config state=failed 继续保留原始观察；本次未核验 O5、WAN 连通或注册/WAN变更。
尚未提交/推送本轮修改；下一步审核修复，再决定新会话及配置变更审批，
不得把旧 BLOCKED 记录改写成 PASS。

## 已授权旧会话收尾与新 Run 预检（2026-10-13）

用户批准通过正常流程将旧会话收尾为 BLOCKED，再创建新 Run。
操作前 SQLite 在线备份：acceptance-before-new-run-20261013-112126-730226.db；
SHA256：1f6bc8f1a329ef82049ba89dcec76dd0ba5cef6e708473a1a1a77e86602cda77。
备份 integrity_check=ok，位于已忽略的独立验收目录。

通过现有 SkillExecutionService/Coordinator 调用 advance → END_POLICY KEEP →
advance，旧会话 fef38db6-5988-43b1-9a60-3750a3e2df32 最终为 BLOCKED，
旧 Result=BLOCKED / DRAFT，未锁定。没有把旧阻塞判为 PASS。
只追加正常收尾事件及派生评估；原 case/skill/parameter 快照和版本字段逐值一致，
原执行事件前缀逐行一致。未启动应用 lifespan，因此未触发旧任务重启恢复。
这是现有业务 Service 的现场验收，不是浏览器或 HTTP 启动/重启验收。

- 新 Session：cc0d9351-50b2-452e-952d-f63fa00bc222。
- 新 Run：55ee49bf-2fc0-4930-9d3d-8c6856f55b50。
- 新 Result：588bf0e5-a437-40d0-b0b3-768d2c479c50。
- PREFLIGHT / AUTOFIND / SNAPSHOT 均 PASS；FREE_ID 为 BLOCKED。
- 新会话暂为 RUNNING / DRAFT；未推进 FINISH，也未批准配置变更。
- 6 份平台证据均通过文件大小及 SHA256 校验；未声称本轮 HTTP 下载验收。
- 正式 data/test_workbench.db 的 SHA256 未变；验收库 foreign_key_check 无异常。
- 删除注册、注册和 WAN 下发均未执行，设备配置写入 0。

FREE_ID 的已存只读端口证据显示表格位置为「0/ 2/9」，含斜杠旁空格。
当前 _port_read_valid 和 used-ID 提取使用固定「0/2/9」正则，不能匹配该格式。
证据中端口有 17 个 ONT；未将“解析失败”误报为“没有空闲 ID”，也未擅自选 ID。
下一步应 TDD 修复端口位置格式识别及 used-ID 提取/占用校验的一致性，
保留严格目标匹配；本轮只定位原因，未修改业务代码。
完整执行闭环继续 HOLD；新任务阻塞记录保留，不绕过门禁。

## 端口空格格式兼容修复（2026-10-13）

按批准的下一步采用 TDD：新增端口格式测试修复前 6 failed / 3 passed，
失败覆盖含空格/制表符端口的空闲 ID 识别、注册占用 ID 判断及满端口判断。
修复后解析/动作/端口相关测试 43 passed（0.95s）；完整后端回归
563 passed（311.42s）。独立只读代码审核无 Critical/Important/Minor 问题，
审核者自行运行端口与既有动作/审批保护测试 23 passed。

最小改动为 MA5800Actions._port_pattern：仅允许斜杠两侧水平空格/制表符，
端口读取验证、已用 ID 提取和注册前占用检查共用该规则。F/S/P 数字分量
与 ID 边界保持严格，0/2/100 不会匹配目标 0/2/10；已占用 ID 仍阻止注册。
SN 校验、配置审批、命令构造、数据库设计、快照和 LOCKED 规则未修改。

本轮未连接设备、未修改现场验收库或旧 Run，未重试已有 FREE_ID 阻塞会话；
这些软件测试不等于现场复验或完整业务 PASS。本轮修改尚未提交/推送，
main 未修改。下一步审核固化修复后，独立只读复验端口查询；任何注册/WAN
配置变更仍须核对目标、空闲 ID 及实际影响范围并得到明确批准。

## 端口修复后独立现场只读复验（2026-10-13）

代码基线 7439b2ef90fa9601e3f6b0316b4529a294d7e165。读取新会话
cc0d9351-50b2-452e-952d-f63fa00bc222 的冻结 RuntimeBinding 与参数，
直接调用真实 BoundExecutionRuntime：snapshot_ont / find_free_ont_id 均 PASS，
error_code=None。没有启动应用或推进已有会话，旧 FREE_ID BLOCKED 事件保留。

- 规范化 SN 与冻结 SN 一致；0/2/9、ONT-ID 14、Profile 10/10。
- 注册状态 online / failed / match；Config state=failed 仍保留原始观察。
- PPPoE：IP Host index 1、VLAN 1000、CONNECTED。
- IPoE：IP Host index 2、VLAN 1000、CONNECTED。
- 当前 WAN index 与冻结测试参数（PPPoE=0、IPoE=1）不同；不覆盖现有 WAN，
  不以 Connected 代替 Ping/O5/Internet PASS。解析出的 service-port 数量为 0，
  本轮不把这个值当作完整所有权或删除影响范围证明。
- 空闲 ONT ID 观察为 16，仅为本时点只读查询，不是注册授权或永久预留。
- 4 份独立文本/PNG 证据的大小及 SHA256 校验通过，位于已忽略的
  data/local-runner/port-readonly-recheck-20261013/；不是新增平台 Evidence。
- 验收库及正式库 SHA256 均前后一致；设备配置写入 0。

结论：两项解析兼容修复的现场只读复验 PASS；完整业务执行继续 HOLD。
下一步先明确现有注册/WAN 保留或替换策略及 service-port 影响范围，
任何使用 ID 16、删除 ONT 14、重新注册或 WAN 下发都必须另行明确批准。
本轮仅追加文档，未提交/推送，未修改业务代码或历史 Run。

## service-port 影响范围只读核对（2026-10-13）

用户同意保留现有注册/WAN，核对影响范围。离线检查上一轮最新真实只读
证据 f14b1f3059004b05850c6690367a00a4.txt 的 display service-port 段，
原文包含 Huawei Switch-Oriented Flow List：

service-port 288，VLAN 1000，gpon 0/2 /9，ONT 14，GEM 1，
FLOW TYPE vlan / FLOW PARA 1000，STATE up；Total : 1。

用现有 parse_service_ports 重放该证据，结果数量仍为 0。该解析器仅支持
精简的六列数字行，不能识别现场带 common/gpon/vlan/state 列的真实表格。
因此先前“解析出的 service-port 数量 0”不代表设备没有 service-port；
已定位影响范围包含 service-port 288。原平台快照不回写，原证据继续保留。
snapshot_ont 返回 PASS 仅说明现有动作门禁通过，不足以证明配置快照完整。
在修复真实表格解析及非空表格不可静默当空的门禁前，不允许基于该快照删除注册。

WAN 编号补充：参考技能记录指出 MA5603T 的零基命令索引 0/1 会显示为
WAN Index 1/2；本次 MA5800 的实际索引语义还需核对，不能仅凭显示 1/2
认定冻结参数 0/1 与当前配置冲突，不应据此覆盖现有 WAN。

本轮仅读取已有证据并离线重放，没有新增设备连接/配置写入，没有修改业务代码、
数据库或历史 Run。完整配置变更门禁继续 HOLD。建议下一步 TDD 覆盖现场
完整 service-port 表格、精简格式兼容、严格目标归属及解析失败拒绝；等待批准。

## service-port 完整表格解析及失败保护修复（2026-10-13）

用户批准继续，范围仅为解析、快照/归属门禁及测试。采用 TDD：最终初始用例
修复前 15 failed / 5 passed；首次修复后相关 63 passed。独立审核指出
非数字未知内容及异常 Total 可被忽略，亲自补测复现 3 failed / 20 passed；
进一步补测标题缺失和尾行后未知内容，复现 2 failed / 23 passed。
最终统一验证整段输出的命令包络、已知表头/分隔线、完整 Total、已知说明行；
未知内容、截断完整表格、数量矛盾和重复 service-port 均拒绝，不当作空表。
保留六列精简格式；空表必须由合法 Total : 0 明确证明。

快照采集和已批准变更前的所有权检查共用严格 F/S/P + ONT ID 验证；
异常或归属不一致时 BLOCKED，不生成假完整配置快照。未改变 SN 校验、
配置审批、命令构造、数据库设计、历史快照或 LOCKED 规则。

初轮全量出现集成测试失败，随后单模块复现 5 failed / 5 passed：
- test_api_to_runtime_to_evidence_chain[False-None]。
- test_api_to_runtime_to_evidence_chain[True-None]。
- test_api_to_runtime_to_evidence_chain[False-PPPOE]。
- test_repeated_connection_wait_does_not_enter_recovery。
- test_external_failure_is_blocked_and_retains_evidence[selector]。
原因是该文件 Lab.cli 的 service-port 查询替身返回通用 Command executed
successfully，不能证明空表。仅增加两行明确返回 Total : 0，原断言全部保留，
没有让生产解析接受通用成功冒充空表，也未修改测试期待状态。

最终相关动作/解析/端口/API 集成测试 78 passed（27.06s）；重新完整后端
回归 588 passed（313.17s）。独立复核无剩余 Critical/Important/Minor，
审核者自行运行 service-port 与 binding acceptance 测试 35 passed。

最终解析器离线重放此前完整真实脱敏证据（包含 Huawei 说明尾段），正确输出
service-port 288 / VLAN 1000 / FSP 0/2/9 / ONT 14 / GEM 1 / USER VLAN 1000。
这是历史证据离线重放，不是新的现场查询或平台 Run；旧错误快照不回写。
本轮没有连接设备、修改现场验收库/正式库或推进会话。main 未修改。
本轮业务修复及文档尚未提交/推送；完整执行闭环继续 HOLD。
下一步审核固化修复，再进行独立只读现场复验；任何注册/WAN 配置变更
仍须明确批准，并使用能够证明完整影响范围的新快照。

## service-port 修复后的现场只读复验（2026-10-13）

代码基线 598b7ff5d185e54592c34b5ea1268466f43b965c，使用已有新会话
cc0d9351-50b2-452e-952d-f63fa00bc222 的冻结目标直接调用真实 Runtime，
重新执行 snapshot_ont 与 find_free_ont_id，两项均 PASS、error_code=None。
这是新采集的独立只读 Runtime 快照，不是覆盖旧平台 ConfigurationSnapshot，
也未启动应用、推进旧会话或创建平台 Evidence。

- SN 与冻结 SN 一致；0/2/9、ONT 14、Profile 10/10。
- 注册状态 online / failed / match；Config failed 仍作为观察保留。
- PPPoE 显示 index 1、IPoE 显示 index 2，均 VLAN 1000 / CONNECTED。
  未据显示编号推定命令索引冲突，未测试 O5 或 WAN Ping/网络连通。
- 本次新快照确实包含 service-port 288：VLAN 1000、FSP 0/2/9、ONT 14、
  GEM 1、USER VLAN 1000；字段逐项核验通过，非此前旧证据的离线重放。
- 当前空闲 ONT ID 为 16，尚未授权注册，也没有永久预留。
- 本次 4 份新文本/PNG 证据在已忽略的 port-readonly-recheck-20261013 目录，
  文件大小及 SHA256 全部通过；保留该目录此前的证据，未覆盖。
- 验收库和正式库的文件 SHA256 前后一致，历史 Run/事件/快照没有改写。
  设备配置写入 0；未删除 ONT 或 service-port，未下发 WAN、未修改 LAN/NAT。

结论：SN、端口及 service-port 解析修复的现场只读门禁复验 PASS；完整
平台执行闭环仍未完成。可以保留现有注册继续核验 O5 与分 WAN 连通性，
但删除 ONT 14/service-port 288 或用 ID 16 重注册仍需独立核对完整变更预览
并获得明确批准；当前只读成功不等于配置操作或恢复路径获准。
本轮仅追加验收文档，未提交/推送。

## 保留配置的真实 PON 与分 WAN 业务诊断（2026-10-13）

代码基线 598b7ff5d185e54592c34b5ea1268466f43b965c，继续使用已有会话
冻结的 ONU Web 目标和操作系统凭据引用，不启动平台、不改配置或旧数据。
首次登录后的页面未直接确认 SN；按现场实际 Device 链接进入 status.asp，
读取序列号字段后与冻结目标一致，才继续。认证成功不被当作身份匹配证据。

使用项目现有 NeutralPlaywrightSurface/NeutralONUWebAdapter 本地执行，
PON 只读采集使用现场已观察到的 status_pon.asp 链接。截图已人工核对确为
Status > PON，不使用 WAN 截图替代光功率证据。两次读数均 O5 / ONU ID 14：
- 初次 TX 2.322856 dBm、RX -13.496925 dBm。
- PPPoE 补测前 TX 2.305779 dBm、RX -13.477537 dBm。
光功率仅记录测量值，未新增合格范围或据两次采样声称长期稳定性。

ONU Web 两路 WAN 均 VLAN 1000/up：IPoE nas0_1，PPPoE ppp0_nas0_0。
诊断下拉实际选择 IPoE value 130817（截图显示 nas0_1）、PPPoE value
65536（截图显示 ppp0），没有使用 Any/默认接口作为分路证据。
每个目标均为 4 发 4 收，0% 丢包；平均 RTT：

| WAN | 网关 | 公网 IP 1.1.1.1 | 域名 www.baidu.com |
| --- | --- | --- | --- |
| IPoE | 1.913 ms | 55.135 ms | 8.865 ms |
| PPPoE | 1.679 ms | 58.574 ms | 18.824 ms |

首次辅助验收脚本把 PPPoE 的「up + 在线时长」误判为未在线，跳过了 Ping，
没有报告假失败或假 PASS。只修正已忽略临时脚本的严格状态格式识别，
再次仅补测 PPPoE；未改产品代码或测试断言。初轮生成 12 份证据，补测轮
生成 10 份（含再次 PON/WAN 采集），共 22 份脱敏 PNG/文本，大小与 SHA256
均经现有 EvidenceStorage 保存后校验。目录为 main 已忽略的
data/local-runner/web-business-20261013/independent-probe/cc0d9351-50b2-452e-952d-f63fa00bc222/。

关键截图：
- PON：5ddf8ad4-ddb7-4ce8-9c42-de6520792d63.png，补测 PON：af9c22f0-b2ba-4239-a373-28dd606c36b3.png。
- IPoE 域名 Ping：01240b6b-db12-436c-98fa-7db1c826e118.png。
- PPPoE 域名 Ping：2a14e27b-9191-4fb9-bf85-5257d414283b.png。

验收库和正式库文件 SHA256 前后不变，配置写入 0。两路内置 Ping 与 O5
现场诊断 PASS，但不是新平台 Run/Evidence 持久化、注册/WAN 下发或报告归档
闭环验收；旧 BLOCKED 会话、Result/快照不回写，未 LOCK、未生成新报告/归档。
本轮未验证电脑侧 DHCP/DNS/NAT、HTTP/HTTPS 或恢复/重注册路径。
OLT Config state=failed 仍保留为观察，不能因业务 Ping 通过而删去。
本轮仅追加文档，未提交/推送，未修改业务代码。后续先固化本轮验收记录，
再评审平台完整闭环与配置变更审批，不把当前诊断成功当作自动批准。

## 审批预览 service-port 影响范围修复（2026-10-13）

本轮只修复可信 ConfigurationSnapshot 中 service-port 未进入配置变更审批
预览的问题，不实现 service-port 创建/生命周期、前端接入或设备配置操作。
SkillCoordinator 在生成变更预览前读取冻结快照，校验每条记录的 ID、规范
FSP、ONT ID 和重复项，仅提取有效目标 FSP/ONT 的 service-port，并排序后
传入 affected_service_ports。注册使用空闲新 ONT ID 时不继承旧 ONT 端口。
已知空表保留兼容；缺失、异常或前导零 FSP 等不确定范围拒绝生成审批。

新增测试验证单条/多条/空表、相邻端口或 ONT 排除、快照与哈希不变、旧空
范围哈希无法批准新的非空预览，以及异常范围拒绝且不创建审批或启动动作。
测试执行器禁止真实设备调用；本轮未连接设备、启动现场平台或改写历史库。

TDD：首次新增范围测试 11 failed / 2 passed；首次修复相关测试 55 passed。
独立审核发现前导零 FSP 边界后，补充反例得到 2 failed / 13 passed，再修复。
最终相关测试 57 passed（84.12s）；独立复核范围测试 15 passed（24.98s），
无剩余 Critical/Important 意见。最终完整后端回归 603 passed（326.85s），
使用 no:cacheprovider、PYTHONDONTWRITEBYTECODE 和独立临时目录。
此前一次全量运行主动中断，不计作通过结果。

本轮未改数据库结构、Snapshot/LOCKED 规则、设备命令或恢复保护；完整 WAN
恢复仍不支持，完整平台执行闭环继续 HOLD。本轮未改前端、未运行前端测试。
修复、测试及本记录尚未提交/推送；下一步先审核固化本轮修复，再逐项评审
剩余闭环缺口，不能据本次测试通过批准现场注册、WAN 下发或恢复操作。

## service-port 生命周期 Task 1 部分实施与协议采样（2026-10-13）

设计 ae11ecfe98dfe30567f12c84ad19aa1a292e24d0 已获书面批准，用户选择当前
会话逐项实施。先按计划缺样本分支加入独立 PortRead/详情边界：目前只返回
UNCONFIRMED，不能把简表、空 Total、通用成功或未验证详情认定为完整映射
或全局 ID 空闲。查询摘要绑定目标 hash 与原文本 hash，不留原文或伪造 Evidence。
本边界尚未接入自动创建路径；不表示完整协议解析已经实现。

离线基线端口/transport 33 passed（0.79s）；新测试 RED 12 failed（0.71s），
GREEN 加端口/transport/配置回归 72 passed（1.65s）；完整后端 615 passed
（311.15s）。未改前端、数据库结构、既有命令白名单或配置字段。

用户随后单独批准 OLT 只读详情、Profile/GEM、候选 ID 和必要命令帮助采集。
使用会话 cc0d9351-50b2-452e-952d-f63fa00bc222 的冻结绑定与系统凭据引用，
每次连接核对固定 SSH 指纹、SN、FSP 0/2/9、ONT 14 和 Profile 10/10。
未启动应用，不推进该旧会话，不改旧事件、Result 或配置快照。

当前现场事实与历史不同：
- 全局查询 service-port 288 返回 Service virtual port does not exist。
- 候选 289 已被 0/2/9、ONT 15 占用，不能用于目标 ONT，也不自动认领。
- 重新查询目标 ONT 14 清单，当前为 service-port 290，VLAN 1000、GEM 1、
  user VLAN 1000、up；完整详情为 common/gpon、Flow type vlan、translate。
- Profile 10 为 GPON、VLAN mapping、ETH GEM 1，包含 VLAN 1000 映射。
  上述读数不是创建授权；288 不自动预留，290 不被自动改写或清理。

头两次帮助读取等待普通完成提示导致 CommandTimeoutError，明确不计为通过；
连接均关闭。最后一次仅发送带问号的未提交帮助行，截取文本后直接关闭 SSH，
成功取得显式端口 ID + VLAN/GPON/ONT/GEM/multi-service/user-vlan 的可执行
语法提示及 tag-transform 选项；没有按 Enter 执行配置。未因帮助读取成功
推断所有转换模式、完整恢复或创建能力已经支持。

4 个独立采样目录分别生成 8、4、4、6 份脱敏 TXT/PNG，共 22 份，大小及
SHA256 经 EvidenceWriter 保存后逐份校验。根目录 main 已忽略的
data/local-runner/service-port-detail-probe-20261013/；目录分别为
6050c8ab41ba47758c123bf62f0dbf0b、4bf3d13721854a9da7baae5d6b226598、
77a1a91f50984acb920f738fa1526117、4d90e949a5294a77afb45a495006be8a。
每轮验收库和正式库 SHA256 前后不变，SSH 已关闭，设备配置写入 0。

Task 1 尚未全部完成：完整详情/Profile 解析、参数契约与冻结配置、创建
白名单和转换规则仍需基于真实样本继续 TDD。Task 2–7 未开始，不把未确认
边界当作可用的生命周期功能。历史 288 快照不回写为 290；任何后续操作
都必须新建计划和新采集范围。当前代码/测试/计划/本记录未提交或推送。

## 生命周期 Task 1 完整读取/契约/编码验证（2026-10-13）

继续已批准计划，补采显式 tag-transform translate 的只读命令帮助：返回
<cr> 可执行语法提示；仅输入问号，未回车执行配置，随后关闭 SSH。新增
7b4f1999a8374203bcb46aff1fc21971 目录的 6 份脱敏 TXT/PNG 大小/SHA256 通过。
验收库/正式库前后 hash 不变，配置写入仍为 0；累计该采样根目录 28 份证据。

实现 MappingSpec/ServicePortMapping/ServicePortProfile 冻结契约：明确 VLAN、
GEM、用户 VLAN、候选 ID、translate/multi-service；拒绝 bool、字符串数值、
越界值、未知属性和非规范 FSP。候选 ID 不参与语义 mapping_key，但属于独立
创建参数，不自动分配。新 profile 仅绑定现有 OLT 引用；可选字段缺省时旧配置
序列化及 SHA256 不变。新会话冻结 profile，后续配置修改不影响旧绑定。

详情仅在完整范围响应、全部字段与已支持属性一致时 FOUND；按 ID 的明确
不存在响应才 ABSENT；其他未知/不完整/冲突输出为 UNCONFIRMED。Profile/GEM
仅接受完整 ETH/VLAN 映射；重复字段、未知内容、缺行和未验证队列模式拒绝。
白名单新增全局 ID 查询、Profile/GEM 查询和显式 ID+translate 创建编码。
仅编码、未注册为可执行平台动作，未改变已有运行/审批流程。

脱敏 fixture 来源为已保存实测协议，端口/FSP/ONT/profile 名替换为虚构值，
不提交原始现场证据、账号、密码、地址、数据库或生成文件。离线重放实际
已保存证据同样得到 288 ABSENT、289 FOUND/ONT15/down、290 FOUND/ONT14/up；
Profile 10 为 GEM1 的八条 VLAN 映射，包含 1000。该重放用虚构绑定 hash 进行
孤立解析验证，不产生新 Snapshot、审批或设备操作授权。

TDD 新契约/详情/命令首次 RED 37 failed / 36 passed（1.58s）；中间失败含
未完整应用补丁、常量名与块尾空行，查明代码原因修复，未弱化测试。
初次相关 GREEN 139 passed（6.53s）；再补结构反例 RED 4 failed / 31 passed
（0.99s），整包校验后相关 GREEN 143 passed（6.42s）。最终完整后端
680 passed（323.02s）；未改前端业务，本阶段未运行前端测试/构建。

范围裁定：暂限已有真实样本证明的 common/gpon、VLAN flow、multi-service /
translate、基线属性及队列模式；其他有效但未验证的模式仍可能 BLOCKED，
不为兼容而忽略字段。缺省 profile 从序列化省略以保留老配置 hash，消费者
须按可选字段处理。Task 1 代码与验证已完成，提交仍待用户指令；Task 2–7
尚未实现，整体独立审核安排在最后，当前不宣称生命周期或恢复闭环已完成。
本轮未提交/推送/合并，main 未修改，原 Snapshot/LOCKED/报告归档保持原规则。

## 生命周期 Task 2 追加式资源账本验证（2026-10-14）

Task 1 后续已按授权提交为 53b8e4495cd0d20dd5babb42fcc9111293d9d29e 并同步
远端 feature；前节的“等待提交”为当时状态。Task 2 从此提交继续，仅新增纯
事件重放与清理候选筛选，不新增数据库表、迁移、依赖或设备动作。

沿用 ExecutionEvent 和 Repository.events(session_id) 完整、有序、连续事件流，
处理版本 1 的复用、创建/删除意图、核验、不确定和 KEEP 事件。幂等键为
operation_id:event_type；相同已持久化事件不重复生成资源，冲突键、未知版本、
缺序、非法状态转移均拒绝。投影冻结，不修改已有事件、旧快照或历史结果。

只有本会话已核验创建、具有创建事件引用和前后证据、未被保留 WAN 消费者
引用的 ACTIVE 资源进入候选。REUSED、未核验、不确定、KEEP、已删除资源
不具备候选资格；混合会话及重复资源投影拒绝。整会话端口事件固定于同一
OLT 绑定、FSP、ONT 和基线，避免第二映射带入另一设备或另一基线。

范围裁定：完整事件流而非 PORT 事件子集用于重放；CREATED 消费者在创建
意图冻结，同映射双 WAN 在后续 Task 3 一起规划。REUSED 可累计消费者但不
获得所有权。不确定创建不自动认领；不确定删除可接受只读确认缺失的后验，
再次删除意图必须使用新操作、新审批和不与旧前验证据重叠的证据。
代价：部分事件流、多 DUT 会话或事后扩增 CREATED 消费者会被阻塞，需要
另行明确契约；Task 4–6 仍须核验现场身份、证据文件/hash、时效和审批。
纯投影不是现场所有权永久保证，也不是执行删除的授权入口。

TDD：上一轮初始 RED 38 failed（2.39s），相关 GREEN 51 passed（10.22s）；
补重复映射及中断恢复反例 RED 3 failed / 40 passed（3.15s），相关 GREEN
56 passed（15.25s）。本轮补会话/重复投影反例 RED 4 failed / 43 passed
（2.87s）；范围校验修复后仅剩重复投影反例失败，1 failed / 46 passed
（2.44s）；完成修复后账本和 Repository 相关 GREEN 60 passed（11.88s）。

验证命令：python -m pytest backend/tests/test_service_port_ledger.py
backend/tests/test_skill_execution_repository.py -q -p no:cacheprovider
--basetemp=C:/Users/admin/Documents/Codex/lrb-tests/port-ledger-final-green-20261014
--tb=short。完整后端命令：python -m pytest backend/tests -q -p no:cacheprovider
--basetemp=C:/Users/admin/Documents/Codex/lrb-tests/port-ledger-full-20261014
--tb=short；结果 727 passed（332.39s），退出码 0。git diff --check 通过；
仅有 Git LF/CRLF 转换提示。前端未修改，本阶段未运行前端测试或构建。
未连接设备、未写正式/验收数据库、未执行创建/删除动作。

Task 2 实现已通过相关及完整后端测试，未提交、推送或合并，提交仍待用户指令。Task 3–7
未开始，整体独立审核仍在 Task 7；不宣称 service-port 现场闭环已完成。

## 生命周期 Task 3 保留已有注册的新计划验证（2026-10-14）

Task 2 随后已按用户指令提交 79a1231e932a383168beace807e3abe56de41bbf，完成
门禁再次 60 passed（13.16s）；未推送/合并。Task 3 从此干净基线开始。

新增 build_service_port_plan 返回 version=2 的冻结计划，新会话仅在已有
RuntimeBinding 中提供完整 IPOE/PPPOE 映射时选择；没有新 profile 的旧绑定
继续 version=1。部分 profile、业务 VLAN 不符或同一映射候选冲突直接拒绝，
不补默认 GEM/端口 ID，不让请求覆盖映射。configuration.py 沿用 Task 1 字段，
无需新增配置或修改旧配置 hash。已安装 CATALOG 定义和旧 build_plan 不变。

新计划取消自动发现、空闲 ID、删 ONT 和注册节点，先核验已注册目标的
SN/FSP/ONT、line/service Profile、online/match，再查询实际线路 Profile 的
ETH/VLAN/GEM 映射。重复字段、失败标记、截断、身份/Profile/GEM 不符均
BLOCKED。仅新核验入口强化协议完整性，不修改旧解析器行为。注册证据以
MA5800 来源和解释记录：现有注册证明目标已上报，不伪造 autofind 记录。
沿用旧 E1 证据组名字，读取者不能据此推断本次执行了 autofind 命令。

新计划 RESTORE 在任何动作之前 BLOCKED；结束仅提供 KEEP/CANCEL，完整
WAN 自动恢复仍不支持。顺序测试保留 ISOLATE_IPOE 人工确认；并发模式保留
SWITCH_IPOE/SWITCH_PPPOE，不通过 remove_test_services 删除共用映射。共享
映射一次规划 IPOE/PPPOE 消费者，不同映射分开。KEEP 不授权自动写入，也
不跳过后续逐动作预览/审批。协调器拒绝没有 MA5800 注册及 GEM 核验证据的
PASS 返回，不让未证实的注册继续推进，旧空闲 ID 事件不覆盖 version=2 目标。

范围裁定及代价：完整双 WAN profile 才可用新路径；要求 RESTORE 的用户仍
受阻塞；版本 2 的通道 inspect/create/verify 节点仅为 Task 4 预留，尚无可执行
写入处理器，当前会安全阻塞，不能宣称现场通道闭环已完成。旧计划不升级。

基线协调器/绑定 19 passed（22.38s）。TDD 初次 RED 16 failed / 4 passed
（12.21s），补成功/证据门禁 RED 18 failed / 4 passed（14.24s）；第一轮相关
GREEN 41 passed（35.35s）。协议反例 RED 3 failed（3.74s），新入口检查后
相关 GREEN 60 passed（37.61s）。命令：python -m pytest
backend/tests/test_service_port_plan.py backend/tests/test_skill_coordinator.py
backend/tests/test_local_runner_binding.py backend/tests/test_local_runner_runtime.py
-q -p no:cacheprovider --basetemp=C:/Users/admin/AppData/Local/Temp/twb-task3-final-related-20261014
--tb=short。完整后端命令：python -m pytest backend/tests -q -p no:cacheprovider
--basetemp=C:/Users/admin/AppData/Local/Temp/twb-task3-full-20261014 --tb=short；
结果 752 passed（370.00s），退出码 0。git diff --check 通过，仅有 LF/CRLF
转换提示；未改前端，本阶段未运行前端测试/构建。

本轮无设备连接、无现场命令、无正式/验收库写入、无数据库结构或依赖变更；
Task 3 未提交/推送/合并。Tasks 4–7 未开始，最终独立整体审核仍安排在 Task 7。

## 生命周期 Task 4 复用与审批创建离线验证（2026-10-14）

Task 3 后续已按用户指令提交 7b5c2e64ad816528e10a5e764744399e84d173f0；
完成门禁再次 60 passed（37.45s），未推送/合并。Task 4 从此干净基线实施。

新增 service_port_lifecycle.py、test_service_port_creation.py；调整
ma5800/service_port_contracts.py、ma5800/actions.py、local_runner/runtime.py、
skill_execution/coordinator.py，并同步本记录与实施计划（共八个交付文件）。
复用现有 Repository/ExecutionEvent/Evidence/OperatorInteraction，不新增表、
迁移、依赖、公开 API 或前端业务模块。

只读核验冻结身份、注册/Profile/GEM、目标端口完整详情及全局候选 ID。唯一
完整匹配记录 REUSED，不创建，不取得自动清理资格。重复、同目标/VLAN 的
不同映射、候选在别处占用及不完整输出 BLOCKED；不自行换 ID。Profile 编号
不作为 GEM 编号。同映射的 IPOE/PPPOE 共用一个创建操作及消费者集合。

PortOperation/PortPreview 本任务补齐，冻结 SN、line/service Profile、消费者、
映射、端口 ID、基线/读取 hash；预览显式展示目标和共享影响，全部参与 hash。
PortRead 的证据引用成为 keyword-only，保留原位置参数。新 DTO 尚未发布，
没有历史会话需要回填；未来清理/恢复调用须提供完整目标上下文。

沿用现有确认入口：保存完整预览，等待 CONFIRM；旧 hash/篡改范围拒绝。
审批后再次核验语义状态，先提交 CREATE_INTENT，再进入白名单 I/O；Runner
另查持久预览/意图，缺失时连只读设备 I/O 都不开始。执行器只接受结构化
CREATE 操作，不接受任意 CLI。数据库短事务与设备 I/O 分离，独立 Session
能在设备替身调用时读到已提交意图，提交失败设备写入次数为零。

显式成功回执、同 ID 的完整后验、前后证据文件/行归属/SHA256、当前会话
及基线范围全部一致才追加 CREATE_VERIFIED。不以 prompt 到达替代成功。
超时、命令不确认、后验不符、证据保存/篡改、取消或结果提交失败保留意图/
UNCERTAIN，无自动清理资格，也不自动重发。已核验操作重复调用无额外读取
或写入。新测试没有回写原配置快照、旧 Run/Result 或历史报告/归档。

范围裁定及代价：当前仅支持已验证映射模式；同 VLAN 高级多 GEM 组合保守
阻塞。读取 hash 使用稳定语义状态，预览额外覆盖保存的证据引用，不包含
动态采集时间。成功回执目前严格限制已支持的显式确认文本，其他真实设备
响应需另行授权采样，不自动当作失败可回滚或成功；现场创建尚未验收。
本阶段不实现清理、自动认领或完整 WAN 恢复，Tasks 5–7 仍待实施/审核。

TDD：初始夹具缺模块导致 13 errors，改为测试体断言后有效 RED 13 failed
（12.92s），事务核心 GREEN 13 passed（13.18s）；Runner/命令证明 RED
4 failed / 13 passed（17.10s）。接线过程中修复测试工作目录与 100KB 夹具
容量问题，改用既有协调器测试的 1MB 测试容量，未放松生产路径/大小保护；
相关 GREEN 49 passed（36.38s）。前验证据篡改 RED 1 failed（2.70s），
取消 RED 1 failed（2.76s），随后相关 GREEN 149 passed（54.40s）；
同 VLAN 冲突 RED 1 failed（2.96s），相关 GREEN 150 passed（54.35s）。
显式目标预览 RED 1 failed（3.22s）；最终相关 GREEN 151 passed（58.32s）。

相关命令：python -m pytest backend/tests/test_service_port_creation.py
backend/tests/test_skill_approval_scope.py backend/tests/test_local_runner_runtime.py
backend/tests/test_service_port_contracts.py backend/tests/test_service_port_ledger.py
backend/tests/test_service_port_plan.py -q -p no:cacheprovider
--basetemp=C:/Users/admin/AppData/Local/Temp/twb-task4-preview-green-20261014 --tb=short。
第一轮全量 773 passed（363.28s）为最后预览身份修正之前的版本，不作为最终
门禁。最终完整后端命令：python -m pytest backend/tests -q -p no:cacheprovider
--basetemp=C:/Users/admin/AppData/Local/Temp/twb-task4-final-full-20261014 --tb=short；
结果 774 passed（348.58s），退出码 0。git diff --check 通过，仅 LF/CRLF 提示；
交付范围共八文件，无数据库、Evidence、ZIP、缓存或构建产物。前端未修改，
本阶段未运行前端测试/构建。

无 OLT/ONU 连接、无现场命令、无正式/验收数据库写入；main 未修改。
Task 4 未提交/推送/合并，最终独立整体审核仍在 Task 7；不宣称现场闭环已完成。
# Task 5 软件验证进展（2026-10-14，未完成）

基线 `a3830fa4d8eae6da628655c994f4bf5132d1246f`；仅在隔离分支工作，未连接 OLT/ONU。

- 核心清理测试 RED 15 failed，GREEN 15 passed：本会话已核验 CREATED 资格、共享消费者保留、两条逐项处理、第二条失败保留部分结果、审批集合不可篡改、已缺失只记录事实、KEEP 不执行设备 I/O。
- 旧 `remove_test_services` 的非空快照列表不再作为删除授权，返回 BLOCKED；旧计划和 Snapshot 不重写。
- 集成测试纠正夹具元组与活跃会话前提后，3 failed / 21 passed；缺失项为 Runner 全局 ID 检查/受审批删除接入和 Coordinator KEEP 记录。KEEP 追加记录随后已接入。
- 实际删除命令与 Runner 守卫的组合补丁被操作审批拒绝，原因是需要更明确的设备删除能力实现授权。补丁未应用；没有新增可执行删除 action，不绕过该限制。现场删除仍需另外确认目标与影响范围。
- 未受阻部分验证：清理、账本、MA5800 动作、审批范围、Coordinator 共 **111 passed / 2 deselected（55.23s）**。排除的是两项尚未接入的 Runner 测试，不能据此声称 Task 5 或完整后端全部通过。
- 当前合法双 WAN 配置最多两条不同映射；使用两条的全部清理和部分失败验证，不虚构第三条资源或放宽冻结映射。批次处理会为后续项记录 NOT_PROCESSED。
- 清理逐条读取采用资源级 hash 的方案仍待 Runner 接入，防止第一条合法删除导致第二条审批因批次自身变化失效。不能识别外部同 ID/同属性无痕重建，现场竞争窗口仍需披露。

状态：未提交、未推送、未合并；Task 5 等待精确能力授权后继续 TDD，Task 6/7 未开始。

## Task 5 继续实施（明确能力授权后，2026-10-14）

用户随后批准了“仅删除本会话已核验创建、无保留消费者、经精确审批的 service-port”能力实现。本次仍仅离线开发/验证；不包括现场写入授权。上节保留此前阻断过程，不代表当前继续阻断。

- 继续前两项 Runner 测试复现 RED：2 failed / 22 deselected（5.53s）。接入全局 ID 读取、资源级语义 hash、持久化批次审批与 DELETE_PENDING 守卫、单条参数化白名单删除及缺失后验后，相关 122 passed（67.85s）。没有任意命令入口或 ONT 删除调用。
- 发现 DELETE 预览误显示 CREATE 标签：新增反例 RED 1 failed / 1 passed，修正 `PortPreview.to_payload` 动作标签，CREATE 原有表示及预览 hash 不变。
- 清理、创建、账本、MA5800 动作、审批范围、Runner、契约、计划及 Coordinator：**204 passed（99.90s）**，没有排除未实现测试。
- 两条合法映射全部处理、第二条失败保留第一条已验证结果；第一条失败则第二条标为 NOT_PROCESSED。跨会话/旧快照不授予删除权，共享消费者及 KEEP 保留；已缺失资源只追加缺失事实，不发删除命令。
- 每项独立提交删除意图后才调用设备边界；超时、后验不符、证据损坏、提交失败及取消不记录成功，不自动重试。读回 hash 包含冻结身份、注册/Profile/GEM 和本资源详情，不因批次自身删除另一条而失效。
- 限制：当前只接受显式支持的成功回执；同 ID 同完整属性的外部无痕重建仍不可观察，不声称跨 OLT 客户端原子性。真实创建/删除与完整平台闭环仍须另行现场审批验收。

完整后端回归：`python -m pytest backend/tests -q -p no:cacheprovider --basetemp=C:/Users/admin/AppData/Local/Temp/twb-task5-full-20261014 --tb=short` → **800 passed（375.68s）**，exit 0。`git diff --check` 通过（仅 LF/CRLF 提示）。本任务未改前端，未重复前端测试/构建；整体最终审核与前端回归留在 Task 7。

范围共八个交付文件：actions.py、service_port_contracts.py、runtime.py、coordinator.py、service_port_lifecycle.py、test_service_port_cleanup.py，以及本验收记录与实施计划。没有数据库、Evidence、ZIP、构建产物或临时文件进入变更集。实现已离线验证、待用户审核提交；未提交、未推送、未合并，main 不变，Task 6/7 未开始。阶段提交门禁尚未完成，不写入 Task 5 complete。

## Task 6：中断恢复与只读详情（2026-10-14）

基线 `6c53c9f945d6ea45ec86723b41f1c2e8a1ca66ba`。Task 5 此前已按用户指令提交、阶段复验 102 passed；旧阶段过程记录保留。Task 6 仅在隔离分支实施，不连接设备、不改 main、不执行迁移。

- 测试先行：首次 13 个夹具设置错误因测试模块没有导入 execution_fixture；修正导入、生产代码不变后，真实 RED 为 13 failed（16.64s）。初始相关 GREEN 102 passed（62.53s）。核对详情缺少最新证据反例 RED 1 failed；本地标记对 LOCKED/CANCELLED/COMPLETED 历史缺少直接保护反例 RED 3 failed。修正后最终相关 **154 passed（121.11s）**。
- 启动 `recover_interrupted` 只重放本地事件。CREATE_PENDING/DELETE_PENDING 追加 UNCERTAIN，不打开 SSH、不取凭据、不重发命令。正常 CREATED/WAITING 会话不动；这些状态若存在持久化悬空意图，则进入 RECOVERY_REQUIRED。未知账本 fail closed，已锁定/终态历史不回写。
- `GET /api/skill-executions/{id}` 增加只读 `service_port_resources`：完整映射、来源、状态、消费者、创建事件、证据引用及最新核对状态/时间。GET 不连接设备、不改事件；旧计划返回空列表，不从旧快照回填所有权；损坏账本返回 409，不泄露原始 payload。
- 新增 `POST /api/skill-executions/{id}/reconcile-service-ports`，请求必须为 `{}`，只能在 v2 / DRAFT / RECOVERY_REQUIRED 会话明确发起。owned、端口列表、命令等额外输入返回 422；复用本机同源校验、串行锁及冻结绑定。仅执行允许列表中的只读全局 ID/身份/Profile 核对，追加 Evidence 和审计记录；“只读”是指设备配置不写，不是声称数据库零追加。
- 创建中断后，即使读回匹配，也不产生 CREATE_VERIFIED 或清理资格。删除中断后，已核验创建的资源若全局 ID 明确缺失，可追加 ABSENT_CONFIRMED；仍存在或无法确认时保留不确定状态。所有路径都不自动解除人工 RecoveryTask、不解锁 Result、不让 Run 自动 PASS、不自动创建/删除或重试。
- 重复 advance / 旧审批 respond 不产生设备 I/O。新恢复审计摘要明确 `automatic_write_authorized=false`，不提供任意命令、手工认领或直接修改资源状态接口。
- 范围裁定：本任务需修改 service_port_lifecycle.py 才能实现已批准接口；独立 recovery 标志仅用于读取，已有写入状态门禁保持原样。正常创建/等待会话不升级，仅有实际悬空意图时中断。没有新增表、依赖或前端代码。
- 待 Task 7 集成检查：资源摘要不等于完整审批预览；必须核验 PortPreview 的 FSP/Profile/业务映射、候选 ID 与消费者到真实 API/前端的完整展示，尤其 `_pending` 的 `target_fsp` 与新预览 `fsp` 键。现场写入门禁尚未通过。

完整后端回归：`python -m pytest backend/tests -q -p no:cacheprovider --basetemp=C:/Users/admin/AppData/Local/Temp/twb-task6-full-20261014 --tb=short` → **817 passed（397.04s）**，exit 0。相关测试 154 passed；`git diff --check` 通过（仅 LF/CRLF 提示）。未修改前端，前端完整验证留在 Task 7。

九个交付文件：coordinator.py、service.py、schemas.py、router.py、service_port_lifecycle.py，两份恢复/API 测试，以及本验收记录和实施计划。没有数据库、Evidence、ZIP、构建产物或临时文件进入变更集。软件实现已离线验证，待用户审核提交；未提交、未推送、未合并，main 不变。Task 7 未开始，真实设备恢复/写入验收未执行；不写入 Task 6 complete，阶段提交门禁仍待完成。

## Task 7：集成验收与现场交接（2026-10-14，验证中）

Tasks 1–6 已分别按用户指令提交，当前功能分支基线为 `c619a4a96cc508b737a5e7d5a7fce482c81f370d`；上文阶段记录保留原时点状态，不代表当前提交状态。main 未修改，Task 7 未提交/推送/合并，现场验收未执行。

### 已批准的最小审批接入

真实 API 反例发现：完整 PortPreview 已保存，但 `_pending` 旧字段筛选遗漏 FSP、Line/Service Profile、映射和消费者。首次三项 RED；扩展完整创建/清理及篡改预览后六项 RED。实际前端此前无该执行器审批消费者，用户随后批准在现有测试执行页最小接入，不新增导航业务模块、会话创建或测试功能。

- API 对单条/批次预览进行严格类型与 hash 校验，返回完整操作列表、目标、候选 ID、VLAN/GEM/user VLAN、转换/业务类型、消费者、创建事件引用、基线/读取 hash 和证据引用；不透传命令、密码或原始 payload。无法核验返回 409。
- 测试执行页输入已有会话 ID 后显式读取；GET 不连接设备。页面逐条展示 CREATE/DELETE 和完整范围，勾选核对后使用当前审批 hash 响应。缺少完整端口预览、LOCKED、未配置 Runner 均禁止审批。
- 审批响应不自动执行、不 LOCK Result。仅独立点击并确认“推进一步”才能调用已有 advance；该操作可能连接设备或执行已经审批的配置动作，不能当作只读查看。错误后清空旧审批，重复点击不会重复提交；没有后台轮询/自动推进。
- 本组件只接入已有会话，不提供新建自动测试会话、任意命令、恢复认领或批量无人值守执行。现有人工结果编辑、LOCK、报告与归档规则不变。

### 离线链路及兼容性

验收测试使用真实 FastAPI/Service/Coordinator/BoundExecutionRuntime、SQLite 事务、事件账本与 EvidenceStorage，仅物理 SSH 传输替换为脱敏协议替身。基线前置步骤由离线夹具提供；这不是现场完整业务测试。

核验同映射双消费者只创建一次，审批无设备动作，独立后验产生 ACTIVE；结果保持 DRAFT，端口创建不代表业务 PASS。设备写后丢失响应进入 CREATE_UNCERTAIN / RECOVERY_REQUIRED，无自动重试/认领。下载每条证据逐一核对 SHA256；旧 LOCKED Run、环境/用例快照、Report 内容和 HTML/Archive 字节保持不变。未完成或未 LOCKED 的新 Run 仍不能生成报告。

首轮兼容测试 8 passed / 1 failed：比较的是归档关联前后的报告响应，差异为合法新增 archive 字段；已将历史基线固定在归档创建之后，没有放松内容/字节校验或修改报告业务逻辑。完整后端、前端回归/构建与独立整体审核正在运行，最终结果另记；不引用前阶段数量作为本阶段结论。

### 现场验收门禁与顺序（待单独授权）

1. 使用新 TestRun 和独立验收库，冻结经人工确认的 OLT/ONU 身份、指纹、Profile、完整两路映射与候选 ID；不得改历史 Run 或测试前快照。
2. 另行取得具体目标的只读授权，先精确复用已有端口并确认 REUSED、证据 hash、原有业务未改变；复用端口永不自动清理。
3. 创建验收另行批准完整 CREATE 预览，明确候选 ID 全局空闲；执行前重新查询。逐一核对持久意图、真实成功回执、完整映射后验和证据。协议未识别或超时即停止，不猜成功、不重试。
4. 清理验收另行批准完整集合，只对本会话 CREATE_VERIFIED 且无保留消费者的资源逐条操作；中途异常保留部分结果和未处理项，不删 ONT、不删复用或跨会话资源。KEEP 验证应为零删除。
5. 中断演练另行授权，确认重启只重放本地事件；显式只读核对不自动授予所有权/重试许可。无痕同 ID/同属性外部重建仍有无法观察的竞争窗口，不声称跨 OLT 操作者原子性。

门禁：软件离线通过不等于现场通过。新生命周期真实创建/清理尚未验收；完整 WAN 自动恢复仍 HOLD，RESTORE 在设备动作前阻塞。不得以端口动作 PASS 或单独 Ping PASS 宣称 IPoE/PPPoE 或整个平台全闭环 PASS。

### 独立整体审核与当前未通过项

一次独立审核覆盖 Tasks 1–7 生产代码、相关测试与本轮未提交文件；无 Critical、无 Minor，三项 Important。没有将设计未列举的输入默认为无风险。

1. 可观察的端口 ID 替换：已核验 53 后被外部换成相同映射的 55，旧验证错误接受 FOUND；反例实际 RED。现在读回必须匹配账本 ID 和允许状态，否则停止进入人工恢复，不重写原资源/快照、不继续 WAN 配置。
2. 创建后取消遗漏恢复义务：创建/验证后在首次 WAN 审批取消，旧路径终结 BLOCKED 却留下 ACTIVE 端口、NOT_REQUIRED；反例实际 RED。现在受核验创建持久化 PENDING 恢复义务，取消还检查追加式账本兜底，无明确 KEEP 不免除人工恢复。
3. 平台清理入口缺失：preview_cleanup/cleanup 与受保护删除 Runner 已实现，但没有正常 Coordinator/Service/API 调用链。清理审批展示测试通过手动构造合法交互验证字段投影，不证明正常用户流程可达。本轮批准限于已有接口的最小前端接入，不擅自新增写入入口或改变结束策略；清理接入需要用户单独确认方案。**这是未通过的闭环门禁，不是已经批准延期的小问题。**

第一次全量回归（两项审核修复前）826 passed（422.14s），前端 60 passed（78.42s），生产构建 PASS；这些数字不替代修复后的最终后端门禁。审核修复反例为 2 failed / 9 deselected（9.44s）；最后修复版本的相关及全量验证另记。

当前结论：待最终修复回归及清理入口范围决策，Task 7 不标完成，不合并、不提交、不推送、不开始现场设备验收。完整恢复仍不在本范围。

### 本轮最终离线验证与交付范围

- 后端最终：`python -m pytest backend/tests -q -p no:cacheprovider --basetemp=C:/Users/admin/AppData/Local/Temp/twb-task7-final-full-20261014 --tb=short` → **828 passed（406.89s）**，exit 0；两项审核修复反例 RED→GREEN，相关 89 passed（124.85s）。
- 前端最终：`npm.cmd test -- --reporter=dot --maxWorkers=1` → **61 passed / 26 files（79.27s）**；`npm.cmd run build` → PASS，exit 0。
- 实际开发代理补验：原 Vite 字符串代理默认重写 Host，审批同源检查收到不一致来源，临时随机端口协议替身测试正确 RED 为 403。改为 `changeOrigin=false` 后保留浏览器 Host/Origin，后端严格同源规则不变。第一次测试初始化错误曾指向无服务的本地默认端口，随后在代理初始化前正确重定向到随机测试端口；没有设备连接。
- 代理测试初放在 src 导致浏览器 TypeScript 构建报 Node 类型缺失；已移到 frontend/tests，未增加依赖或放宽编译校验，最终测试/构建全部通过。
- `git diff --check` 通过；变更集仅以下 15 个交付文件，无数据库、Evidence、ZIP、缓存、临时文件或构建产物。构建输出仅位于既有忽略目录。main 未改，当前 feature HEAD 仍为 c619a4a，所有本轮变更未提交。

修改/新增：backend/app/skill_execution/{coordinator.py,router.py,schemas.py,service_port_lifecycle.py}；backend/tests/test_service_port_lifecycle_acceptance.py；frontend/src/testExecution/{LocalExecutionApproval.tsx,LocalExecutionApproval.test.tsx,TestExecutionPage.tsx,TestExecutionPage.test.tsx}；frontend/tests/LocalExecutionProxy.test.ts；frontend/vite.config.ts；docs/{LOCAL_RUNNER_LIVE_ACCEPTANCE.md,LOCAL_RUNNER_SETUP.md}；docs/superpowers/plans/2026-10-13-service-port-lifecycle.md；docs/superpowers/specs/2026-10-13-service-port-lifecycle-design.md。

结论更新：本轮批准的最小审批接入和两项安全修复已离线验证。**Task 7 完整生命周期门禁仍 HOLD：安全清理核心尚未接入正常平台审批执行流程，需要用户决定接入或明确延期。**没有声称完整平台/现场闭环完成；不标 Task 7 complete，不自动提交/推送/合并，不删除计划账本或 worktree。

## 已批准的清理入口接入与最终收尾（2026-10-15）

上节 HOLD 原因随后经用户“批准”及短设计“确认”获得软件接入授权；仅开发/离线测试，不授权任何现场操作。新入口在既有隔离分支实施，保留全部未提交工作，不修改 main、数据库结构、依赖或历史执行计划。

- `POST /api/skill-executions/{id}/cleanup-preview`：严格 `{}`，从账本推导本会话已核验创建、无保留消费者的完整集合；逐条只读全局 ID/身份/Profile/映射核对并保存真实证据。不删除设备配置。GET 新增 cleanup_available、完整 cleanup_preview、逐条 cleanup_outcome，无设备 I/O。
- `POST .../cleanup-execute`：仅 approved=true 与最新 preview_hash；禁止端口、owned、命令、保留消费者等客户端授权替代。只在 v2 / DEVELOPMENT / DRAFT / KEEP 的 END_POLICY 待确认或 MANUAL_REQUIRED 恢复阶段开放；普通执行、LOCKED、终态和未知资源均不授权。
- 调用链实际可达：Router → Service → 独立小型 ServicePortCleanupFlow → 已有生命周期 → BoundExecutionRuntime 持久审批/INTENT 守卫 → 类型化删除 → 全局 ID 缺失后验。沿用本地同源校验与串行锁。cleanup_flow 仅为可信内部清理接线选项，不改变一般创建/推进权限。
- 预览和执行分别由页面显式点击，执行另需独立勾选“不代表恢复 WAN”。逐条记录成功、异常、未处理项；相同已完成请求零额外 I/O，未完成 STARTED 拒绝重发。清理启动使旧审批失效，结束仍需人工恢复，不自动 PASS、LOCK 或继续测试；没有恢复认领、任意 CLI 或完整 WAN 恢复功能。

测试先行：新 API 初始 RED 13 failed（404），页面 RED 1 failed。初次接线 12 passed / 1 failed，定位清理后复核仍用一般状态限制，修正清理专用调用；相关 50 passed（71.77s），页面 10 passed（8.03s）。读取途中 LOCKED 的反例证明旧证据保存缺少后复核，RED 1 failed / 1 passed（8.56s）；修正后入口 15 passed（25.99s），包括真实 Bound Runner 的持久意图/类型化删除/全局缺失链路，物理 SSH 为离线替身。

新增入口独立审核（不是重审此前已修问题）：无 Critical/Minor，一项 Important 为 I/O 后无条件 `_recovery` 可能覆盖 CANCELLED/COMPLETED/LOCKED。通过实际 API 的三项反例 RED 3 failed（9.50s），增加返回后的 cleanup_stage 检查，禁止追加新成功结论或覆盖终态/LOCKED；已有意图和不确定事实保留，返回 409。审核未判定的现场效果/最终回归/自动恢复等项均明确裁定：现场另授权；最终结果必须读取真实输出；自动恢复/PASS/LOCK/续跑保持禁止。

第一轮后端 843 passed（450.63s）是最终审核修复之前的版本，不作最终门禁。2026-10-15 正在独立临时目录运行修复后的完整后端；前端最终 62 passed（84.74s），生产构建 PASS，exit 0。最终后端结果另记，不提前标 Task 7 complete。

本轮合计 18 个交付文件：前述 15 个文件，加 backend/app/skill_execution/service.py、service_port_cleanup_flow.py、backend/tests/test_service_port_cleanup_flow.py。无数据库、附件、ZIP、缓存、node_modules/dist 或临时文件进入变更集。真实创建/清理/完整平台验收仍未进行；软件通过后等待审核提交，不自动推送/合并或清理 worktree。

### 最终软件门禁结果（2026-10-15）

- 后端：`python -m pytest backend/tests -q -p no:cacheprovider --basetemp=C:/Users/admin/AppData/Local/Temp/twb-cleanflow-final-20261015 --tb=short` → **846 passed（480.91s）**，exit 0，含新增入口全部 18 项反例/链路测试；审核终态复活问题已 RED 3 failed → GREEN，未重新派发审核。
- 前端：`npm.cmd test -- --reporter=dot --maxWorkers=1` → **62 passed / 26 files（84.74s）**，exit 0；`npm.cmd run build` → PASS，exit 0。npm 版本更新提示未执行，不改依赖。
- `git diff --check` 通过（仅 LF/CRLF 提示），main 未修改且干净；功能分支 12 个修改文件、6 个新增文件，合计 18 个。本轮仍未提交、推送或合并。
- 软件 gate：**PASS，待用户审核提交**。此前“平台清理入口缺失”的 Important 已由确认方案的生产接线及实际 API→Bound Runner→证据/账本测试解决；新增入口独立审核仅一项 Important，已测试先行修复。没有遗留 Critical/Important 或延期 Minor。

该 PASS 仅指获批范围的软件离线验收，不表示现场创建/清理已验收，也不表示完整 WAN 恢复已实现。完整恢复仍 HOLD；清理后保持人工核对，不自动锁定或续跑。按阶段提交门禁，未提交前不写 Task 7 complete、不运行完成提交收尾或删除账本/worktree；下一步为用户审核本轮变更并明确提交指令。

## 现场只读身份预检（2026-10-15）：BLOCKED

基线：codex/skill-execution / ed9f33e5b35dde8faba94dc4f24145118442769a；检查前工作区干净。此前 Task 7 已提交 ea2d91d，隔离环境收尾提交 ed9f33e；以上“待提交”表述保留其历史时点。

用户确认设备已连接，仅授权按下一阶段先行只读核对；没有注册、WAN 下发、创建/删除端口、恢复、重启或网卡修改授权。本次使用隔离解释器和现有本机配置/OS 凭据，没有创建平台 Run/Result/Session，没有启动应用或打开数据库。

| 项目 | 当前实测 | 判定 |
|---|---|---|
| 测试网卡 | 以太网 4 为 Up，包含 192.168.1.10/24，另有 192.168.8.254/24 | 仅本机链路/地址事实，不证明 ONU 或 WAN 归属 |
| OLT 管理端口 | 按本机已配置地址 TCP 连接成功后立即关闭 | TCP 可达；SSH 认证/指纹未在本次执行 |
| ONU Web | 登录提交后停留 /boaform/admin/formLogin；正文 `ERROR: invalid username!`，状态页链接 0 | 认证未成功 |
| 当前 ONU SN/型号 | 未能进入状态页 | NOT_EXECUTED，不套用历史设备信息 |
| OLT 注册/Profile/GEM/端口/WAN | 未取得实时 Web SN，安全停止后续查询 | NOT_EXECUTED |
| 平台 REUSED/创建/清理验收 | 未创建新会话，未推进任何动作 | NOT_EXECUTED |

本次有限诊断中累计使用同一已登记凭据提交 3 次，没有猜测其他账号密码；最后响应确认拒绝后停止重试。第一次只读探测因身份字段缺失而停止，页面结构核对确认没有导航，最终脱敏正文解释原因。临时探测将组件正常返回写为 ONU_WEB_LOGIN=True 的早期输出 **不是实际登录成功**，本记录明确更正。

现有 NeutralPlaywrightSurface.authenticate 仅在仍可见密码框时判定拒绝；该固件错误响应没有密码框，因而组件正常返回。这是此次发现的失败响应判定覆盖缺口，不表示已获得 SN、PON O5 或 Web 读取 PASS。没有为赶进度修改适配器或降低身份门禁；后续如需修复须先有独立失败测试与授权。

证据目录：功能分支已忽略的 `data/local-runner/readonly-20261015/dcd5bb2bc0d941a881cf6ff0ac1694bf/`。

- login-response.txt：SHA256 ce34504981d4fd5ea721cfbd308e521afe2adfcdce9f01fca9db436762b42cfa。
- login-response.png：SHA256 5fc2b29a2b03ebb04c2109ffe529914415e68ba4e9979ac45107f4e58078f41d。此 PNG 为脱敏响应文本渲染，不冒充浏览器实截屏或平台 Evidence。

没有凭据值进入文档或证据。未记录人工/自动恢复成功；设备配置写入 0，数据库未打开，main 未修改。不提交或推送本次文档。下一步先由用户确认当前 ONU Web 账号，通过现有隐藏输入入口重新登记后，再核对真实 SN 和 OLT 状态；本次不依据早期历史位置继续执行。

## 确认新凭据后的只读补验（2026-10-15）：BLOCKED，注册位置不一致

同一代码基线 ed9f33e；保留上述拒绝响应和初次登录误判记录，不覆盖历史。用户明确提供并确认账号/密码分隔方式，通过现有隐藏输入登记流程，仅更新本机 Windows 凭据库中的 ONU_WEB 访问对；没有改设备账号、OLT/PPPoE 凭据或配置 JSON。凭据未写入命令参数、脚本、文档或证据。

### 实际观测

| 项目 | 当前证据 | 判定边界 |
|---|---|---|
| ONU Web 登录 | 成功进入设备状态页并取得唯一实时 SN，尾号 CD73 | 登录阻塞解除；不是仅凭 authenticate 未抛异常 |
| Web 版本 | Firmware V3.1.20p11，Hardware V1.0 | 本次读取值，不沿用此前 C999 设备身份 |
| OLT SSH | 现有固定公钥指纹验证后查询并正常关闭 | 未放宽指纹保护 |
| Web/OLT 身份 | 按实时 Web SN 查询，OLT SN 一致 | 只做当前设备定位，不套用旧 ONT ID |
| 旧注册 | 0/2/2，ONT ID 2，Line/Service Profile 10/10 | run offline，config initial，match initial |
| Line Profile/GEM | 完整解析 Profile 10，含 GEM 1 / VLAN 1000 | 未修改共享 Profile；其他映射保留 |
| 已有 service-port | 298，0/2/2:2，VLAN 1000 / GEM 1 / user VLAN 1000，完整详情 FOUND | 旧资源，不是本会话 CREATED，不认领/清理 |
| 当前 ONU 自动发现 | 同一 SN 在 0/2/9，Equipment ID BT-G711AX | 当前发现位置与旧注册不一致 |
| PON 实截屏 | Status → PON（status_pon.asp），ONU State O2 | 未达成 O5，不能判 PASS |
| 光功率 | Rx -14.089354 dBm，Tx 2.208155 dBm | 仅采集，不做未定义阈值的范围合格判定 |
| 其他 PON 读值 | 温度 24.687500 C，电压 3.291600 V，Bias 12.250000 mA；截图显示 LOID Error | 不据此认定唯一根因或已修复 |
| OLT WAN 查询 | 当前旧注册的查询未解析出 WAN 条目 | 不证明 WAN 未配置，也不证明 IPoE/PPPoE 通过 |
| 平台新生命周期 | 未创建 Run/Result/Session，未执行 REUSED 账本/创建/清理流程 | 当前仅组件只读采集，平台现场闭环 NOT_EXECUTED |

自动发现中设备自带时间为 2025-07-13 14:23:57-03:00，与本次 2026-10-15 采集日期不同；保留为设备读值，不拿它证明真实发现时刻或持续时长。仅保存匹配当前 SN 的自动发现摘要，其他 ONU 详情不保存。

### 证据与安全边界

目录：功能分支已忽略的 `data/local-runner/readonly-20261015/929852c327434407ab3df7ae1b6dc9a8/`，共 17 个文件：身份字段、OLT SN 查询、Profile、端口列表/详情、WAN 查询的脱敏文本及文本渲染 PNG，以及 PON 字段、真实浏览器截图和过滤后的发现摘要。

- pon-current-browser.png：真实浏览器截图，保存前调用敏感控件/正文遮挡，画面已检查；SHA256 dbbfd01e3b6e163ffcb46d3dc796e215cfca6706daaf9470998e3f84e7e32d9d。
- pon-current-fields.txt：SHA256 fdc46536b88d7e8b0940b5ddef76606c19c556e5cf938df7c9a9b77280d9d71b。
- autofind-current-target.txt：SHA256 cf9e875fcfce0cfad41a5acb3f02fe470a66ce1b22b8a29957f8507e37031fef。

各生成文件的大小与 SHA256 在采集脚本中逐项核对；证据仅本地文件，不冒充平台 Evidence/Report/Archive。没有账号密码进入证据或提交集。临时采集命令打印的 READONLY_COMPONENT_RESULT=PASS 只表示读操作与解析成功，**不代表 O5、WAN 或整体测试通过**；本次总体结论为 BLOCKED。

本轮设备配置写入 0、数据库未打开；没有重启、恢复出厂、改变网卡/路由、删除旧注册或 service-port，也没有生产代码修改。新增凭据登记只发生于本机 OS 凭据库。当前两份文档未提交/推送，main 不变。

### 下一步需用户决定

1. 无 OLT 配置变更路径：将光纤接回现有注册的 0/2/2，再只读核对是否 online/match/O5；这不是保证自动成功。
2. 保留当前 0/2/9：先单独授权迁移方案和只读变更预览，核对旧注册/端口归属、备份和目标占用后，再逐项批准实际操作。不自动删除旧口 0/2/2:2 或端口 298，也不沿用针对其他设备的历史注册授权。

在选择和必要授权前停止设备操作。完整 WAN 恢复、LAN/NAT 功能测试及登录拒绝检测修复均未在此次只读任务中展开。

## 用户明确授权的旧注册删除（2026-10-15）：完成，尚未新注册

用户选择保留 0/2/9，要求删除 0/2/2 上此台 ONU 的配置，并明确修正为 `undo service-port port 0/2/2 ont 2`，其余删除步骤同意。授权只针对当前 SN 尾号 CD73 的旧 0/2/2:2，不包含共享 Profile 删除或新口注册/WAN。

本次是一次性人工授权的现场维护，不经过自动清理 API；没有修改其资源归属门禁或将旧 service-port 298 伪造为本会话 CREATED。业务代码、平台数据库和历史 Run 均未修改。

### 前置核对与实际执行

1. 从当前 ONU Web 重新读取唯一 SN，再在固定 SSH 指纹验证后按完整 SN 查询：旧位置 0/2/2、ONT 2、offline、Profile 10/10。端口完整列表仅 298；全局详情核对 VLAN 1000、GEM 1、user VLAN 1000，状态 down。保存注册详情、端口列表/详情和 WAN 查询的脱敏前置快照，在写入前再查身份/端口。
2. 持久保存用户批准的精确命令与范围记录后，仅下发 `undo service-port port 0/2/2 ont 2`。设备提示释放 service virtual ports，按已批准范围确认；实际回执 need be deleted=1、have been deleted=1。
3. 删除后目标查询返回 `Failure: No service virtual port can be operated`。现有严格列表解析器将 Failure 拒绝，临时流程安全停止，未继续 ONT 删除；不重发业务端口删除、不把所有 Failure 都视为空。
4. 新建只读连接，独立全局查询 298 得到严格解析的 ABSENT；旧 ONT 范围查询再次给出上述明确无端口响应。重新核对 Web SN 与旧注册仍一致/offline，保存新的核对证据后，只执行已批准的 `ont delete 2 2`。
5. OLT 返回 `Number of ONTs that can be deleted: 1, success: 1`。随后按同一完整 SN 查询返回 `The required ONT does not exist`，设备提示符正常结束。该实际无 Failure 前缀的缺失文案使临时脚本的旧格式断言停止；读取真实回执后，独立核验文件中明确成功/不存在结论，不重试任何删除。

最终确认：业务端口删除命令发出 1 次，ONT 删除命令发出 1 次，各成功删除 1 个对象；298 全局不存在、同一 SN 的旧注册不存在。两个临时脚本的 BLOCKED_OR_PARTIAL 输出是严格后验格式检查停止，不代表两项设备命令被拒绝或可重试。原样保留全部阶段证据，不伪造脚本 exit 0，也不声称已修复解析器。

### 审计证据与恢复边界

目录：功能分支已忽略的 `data/local-runner/old-registration-delete-20261015/21e08dcca0b444a689229a8d4c82e8e7/`，共 32 个文本/渲染 PNG 文件；逐个生成时验证大小与 SHA256，终局另检查成功回执及精确缺失响应。

| 关键证据 | SHA256 |
|---|---|
| delete-old-services-response.txt | ed7050c5b3392d4fa7ec249190fecce1d318262b11db28da04a4de0fb282139b |
| continued-global-port-298.txt | ec60cf2f5fd41b3b1bda9d78d7c3f55151126ce51611e670dea7f834122b4cd8 |
| continued-ont-delete-response.txt | c9c71e44e2a6d144ebeb144de18e9ca2568d12a18a7f52045baabf68f5a7af63 |
| continued-after-registration-by-sn.txt | 45ac7b944bab4ed357f99d6e631ad815bd14062ff67f7f7602c8760179fe0041 |

只移除了旧注册及关联业务端口，没有清空 PON 口、删除 Profile 10/10、恢复出厂或重启 ONU。前置快照保留，可供人工重新注册/重建端口参考；它不是完整 OLT 配置备份，不保证一键或完整 WAN 自动恢复。当前设备在新口的 O5/WAN 尚未验收，不能把旧配置删除成功写为整体测试 PASS。

新注册 0/2/9、选择新 ONT ID、创建端口及下发 WAN 均未执行。下一步先只读查询新口实时发现/占用，再明确批准新注册范围；旧 ONT ID 不自动沿用。此次生产代码/依赖/平台数据库/历史 Run/共享 Profile 均未改动；两份现场文档未提交/推送，main 不变。

## 新口只读占用核对与注册预览（2026-10-15）：待用户确认

同一代码基线 ed9f33e，仅执行 Web 登录/身份读取和 OLT 只读查询，没有 ont add、端口创建、WAN 下发或数据库操作。

- 当前 Web 唯一 SN 尾号 CD73；按完整 SN 查询明确返回未注册，唯一匹配的自动发现记录位于 0/2/9，Equipment ID BT-G711AX。
- `display ont info 9 all` 读取 0/2/9 当前完整列表，解析到 21 个已占用 ID，和设备 total=21 一致：0–18、100、101。按当前支持的 0–127 范围选择最小空闲候选 **19**，不是沿用旧 ONT 2，也不是默认使用 0。
- 现场只读获取 Line Profile 10 和 Service Profile 10，确认存在；Line Profile 完整 GEM 映射包含 GEM 1 / VLAN 1000，没有改共享 Profile。
- 注册预览仅包含：当前 ONU、0/2/9、ONT 19、SN 认证、OMCI、Line/Service Profile 10/10。预览 hash 包含完整目标、Profile、配置绑定 hash 和本轮读取 hash；尚未提交给设备。

```text
interface gpon 0/2
ont add 9 19 sn-auth <当前已核对的完整SN> omci ont-lineprofile-id 10 ont-srvprofile-id 10
```

预览 hash：`53e65724d3abf3d66efe42734b7b15e838c0b8ecc752260563d4d39e93ebfaaf`。
这里是人工维护的注册预览，不冒充已创建的平台 OperatorInteraction 或审批完成状态；本轮没有 Run/Result/Session，不更新历史绑定或生产配置 JSON。

证据目录：功能分支已忽略的 `data/local-runner/register-preview-20261015/b9d97ffda5ba43688f58e8f959e0a6ee/`，12 个脱敏文本/渲染 PNG 文件，采集时核验大小与 SHA256。包含 SN 注册缺失、自动发现、目标端口占用、两个 Profile 和未执行的注册预览。

当前状态：**PREVIEW_READY，NOT_EXECUTED**。需要用户确认新注册后，执行前再次核对当前完整 SN、唯一发现位置、Profile 及 ID 19 空闲；若任何条件改变，停止并重新给出预览。注册后只核对 online/match/O5，不因注册授权自动创建 service-port 或下发 IPoE/PPPoE。端口和 WAN 需后续单独批准，完整恢复仍非本次能力。

## 用户确认后新口注册与只读核验（2026-10-15）：注册成功，配置异常保留

用户回复“是”，批准上述单台 ONU 的 0/2/9:19、SN 认证、OMCI、Profile 10/10 注册及 online/match/O5 核验，不包含 service-port 或 WAN。执行前实时读取完整 Web SN，将其代入前次预览 proposal，以相同 canonical JSON 计算 SHA256，确认与批准的 `53e65724d3abf3d66efe42734b7b15e838c0b8ecc752260563d4d39e93ebfaaf` 完全一致；配置 hash 也不变，不仅依据 SN 尾号辨识设备。

### 前置安全检查与执行结果

1. 固定公钥指纹校验后连接 OLT；完整 SN 查询明确未注册，唯一对应自动发现为 0/2/9。读取完整占用列表并校验设备 total 与解析数量一致，ONT 19 仍空闲；Line/Service Profile 10/10 重新读取确认，Line Profile 的 GEM 1 / VLAN 1000 映射存在。没有修改共享 Profile。
2. 使用现有证据写入器先保存批准范围、前次预览 hash、当前读取 hash、精确命令和最多发送一次的写入意图。通过现有类型化安全命令，只下发一次 `ont add 9 19 sn-auth <已核对完整SN> omci ont-lineprofile-id 10 ont-srvprofile-id 10`。
3. OLT 明确返回 `Number of ONTs that can be added: 1, success: 1`，并返回 PortID 9、ONTID 19；没有重试写入。
4. 按完整 SN 有界只读查询：第 1、2 次 offline / initial / initial，第 3 次 **online / failed / match**。SN、F/S/P=0/2/9、ONT 19、Line/Service Profile 10/10 全部一致。
5. 返回真实 Status → PON（status_pon.asp），字段与实截屏共同确认 **ONU State O5 / ONU ID 19**。Rx -13.936186 dBm，Tx 2.449209 dBm，温度 25.753906 C，电压 3.291600 V，Bias 12.900000 mA；光功率仅记录，不作未定义阈值的合格判定。

### 结果边界与剩余观测

- 注册成功、online、match 和 O5 有实时证据；不是完整 IPoE/PPPoE 或平台 Skill 闭环 PASS。
- **Config state=failed**，PON 截图仍有 **LOID Error**。这两个现象未定位原因，不套用历史设备的 Accepted Observation，也不静默改认证方式、Profile 或其他配置。
- 没有创建 service-port、下发 WAN、改变 LAN/NAT、重启/恢复出厂或打开平台数据库。没有创建/修改 Run、Result、Session、平台 Evidence、Report 或 Archive。
- 这是用户授权的一次性现场维护，使用现有连接/类型化命令组件，不代表已完成平台操作审批、资源归属账本或自动恢复验收。SSH 和 Web 浏览器均已关闭。

### 证据

独立且已忽略目录：`data/local-runner/register-execute-20261015/a7a705574ad747eeb013fdbbcedfd16f/`。共 25 个文件：脱敏前置核对、持久写入意图、注册回执、3 次注册后查询、PON 字段和真实截图、终局摘要。逐项核验文件大小与 SHA256；凭据文本泄漏检查通过，截图已目视确认是 PON 页面，含 O5 / ONU ID 19，非文本渲染替代。

| 关键证据 | SHA256 |
|---|---|
| registration-response.txt | cceae2b44beed1e88d62d428659e900bbd07217b699bb15b92e9f848dc34e940 |
| post-registration-state-3.txt | 022d5e75e840b7cfcc3950b8092f32f2aa87346fa1f79846acc2dbee9a2a58b6 |
| pon-after-registration.png | ea817e359a548623c380c3bd2de8a99bdf24f4dcf3a2d338af3008233430e9ae |

未修改业务代码，因此本轮未重复执行全量单元测试；验证依据为实际设备回执、独立只读字段和截图，不以历史测试数替代现场结果。两份文档仅追加真实记录，未提交/推送，main 不变。下一步可只读排查配置失败并准备端口/WAN 独立预览；任何新增设备写入都需另行批准。

## 配置失败只读排查（2026-10-15）：UNDETERMINED，无写入

用户要求“下一步”后，仅按前述建议读取配置异常与当前业务状态。重新从 Web 获取唯一完整 SN，并还原已批准注册预览 hash 验证身份；OLT 固定公钥指纹校验保持启用。

| 项目 | 实际证据 | 结论边界 |
|---|---|---|
| 注册状态 | 0/2/9:19，Profile 10/10，online / failed / match | 在线且能力匹配，配置失败仍在 |
| PON | O5，ONU ID 19，LOID Error | 注册上线保持，LOID 状态未消除；不据此判为当前 SN 认证失败 |
| WAN | `display ont wan-info 9 19` 返回 `WAN port does not exist` | 当前无 WAN，不是 IPoE/PPPoE 测试 FAIL 或 PASS |
| 业务端口 | 指定 0/2/9:19 查询返回 `Failure: No service virtual port can be operated` | 保留精确设备响应，表明该范围没有业务端口；未改严格列表解析器 |
| 失败详情查询 | `display ont failed-configuration 9 19` 返回 `% Unknown command` | 当前命令不受该视图支持，不把查询失败当作 ONU 根因 |
| 设备命令帮助 | GPON 接口视图、config 视图各读取一次 `display ont ?`，均未列出上述查询 | 尚未取得具体 OMCI 失败项；不声称所有视图/所有诊断方法均不可用 |

注册详情没有给出具体配置失败原因。现阶段没有证据证明缺少 WAN/service-port 导致 Config failed，也没有证据将 LOID Error 与其确定为同一根因；更没有证据据此判固件故障。**配置失败原因仍为 UNDETERMINED**。没有试改 Profile、认证方式或下发 WAN 来验证猜测。

只读帮助读取处理了分页，随后清除待输入命令并确认返回提示符；没有进入 diagnose 模式。两次 SSH 连接均正常关闭，Web 浏览器已关闭。光功率本次 Rx -13.936186 dBm、Tx 2.462778 dBm，仅留作观测，不作阈值判定。

独立证据目录：`data/local-runner/config-failure-readonly-20261015/5200890ba66f4f0abde23169bf191f55/`。第一阶段 13 个文件（注册详情、WAN、失败查询原始拒绝、端口查询、PON 字段/真实截图及摘要），第二阶段增加 6 个文件（目标身份核对、两个视图的完整命令帮助及渲染图）；共 19 个文件，各阶段逐项核验大小/SHA256并检查当前凭据未出现在文本中。未将这些本地文件冒充平台 Evidence。

设备配置写入 0、数据库未打开、业务代码未修改；只追加两份现场文档，不提交/推送，main 不变。下一步可在保留异常的前提下准备独立业务下发预览并请求明确批准，不能称为已确认的修复方案；LAN 端口绑定/NAT 按用户要求留在其他功能测试中，不夹带执行。

## 双 WAN 下发前只读预览（2026-10-15）：PREVIEW_READY，NOT_EXECUTED

用户要求继续下一步，本轮仅生成预览，不执行设备写入。实时 Web 完整 SN 还原原注册预览 hash 一致，配置绑定 hash 不变；OLT 0/2/9:19、SN、Profile 10/10 全部匹配，online / failed / match。重新取得目标无 WAN 和无 service-port 的精确响应，完整解析 Line Profile 10 的 GEM 1 / VLAN 1000，读取确认 VLAN 1000 存在。

候选端口 298 采用独立全局 `display service-port 298` 严格详情解析，状态 **ABSENT**；不因曾删除过旧目标上的同号端口就假定现在仍空闲。本次只查询此一个候选，未扫描全局端口或读取其他 ONU 的无关详情。

待批准范围为同一目标的三个配置动作：

```text
# config 视图：新建同映射共享端口，尚未执行
service-port 298 vlan 1000 gpon 0/2/9 ont 19 gemport 1 multi-service user-vlan 1000 tag-transform translate
# interface gpon 0/2：使用不同 IP host index，尚未执行
ont ipconfig 9 19 ip-index 1 dhcp vlan 1000 priority 0
ont ipconfig 9 19 ip-index 0 pppoe user-account username <已登记用户名> password <已登记密码> vlan 1000
```

两个 WAN 的 GEM/VLAN/user-VLAN/translate 完全相同，因此预览只新建一个 298，明确 consumers 为 IPOE、PPPOE，不重复创建两条相同映射。PPPoE 凭据仅在内存中供现有类型化命令验证，预览保存凭据绑定引用与占位符，不保存账号密码或其命令明文。

预览 SHA256：`7bc1667955221fdc1df90ea472d3d553c438cd7b3eb0826ac6b21d7f49ac85ec`，包含完整目标、配置绑定、当前读取 hash、候选资源、WAN host index、排除项和执行限制。它是人工维护预览，尚未获得本次设备写入批准，不冒充平台审批、会话资源账本或自动回滚能力。

批准后仍需写入前实时重查完整身份、Profile/GEM、VLAN、候选 298 空闲和目标现状。任何变化均停止复核；每条配置最多发送一次，不明确回执只读核对，不能自动重试或删除。后验需读取端口完整详情、OLT WAN 与 ONU WAN 两侧状态；建链成功也不等于 LAN/NAT 或电脑上网通过。

Config failed / LOID Error 仍为未解决观测；没有证据把下发 WAN 认定为其修复。范围明确排除修改共享 Profile、LAN 绑定/NAT、电脑网卡/路由、删除旧资源、重启/恢复出厂、平台数据库和历史 Run。

证据：已忽略的 `data/local-runner/dual-wan-preview-20261015/f7c29c7f9cd44dbc9fac545d0079f565/`，共 14 个脱敏文本及渲染 PNG（当前注册、WAN 缺失、端口缺失、Profile、298 全局缺失、VLAN 1000、未执行预览）。逐项核验大小与 SHA256，当前 OS 凭据文本泄漏检查通过。连接已关闭；设备配置写入 0，数据库未打开，代码未修改，仅两份文档更新且未提交/推送，main 不变。等待批准后再执行，不将预览标为测试 PASS。

## 已批准双 WAN 配置与最终交叉核验（2026-10-15）：IPv4 建链 PASS WITH OBSERVATIONS

用户回复“是”，明确批准上述同一预览内的 298 创建、IPoE index 1、PPPoE index 0 及双侧只读核验。原预览 SHA256 `7bc1667955221fdc1df90ea472d3d553c438cd7b3eb0826ac6b21d7f49ac85ec`，执行前用实时 Web 完整 SN 还原 canonical JSON 校验一致，配置绑定 hash 未变。OLT 连接继续固定公钥指纹校验。

### 执行顺序与真实回执

1. 重验 0/2/9:19、完整 SN、Profile 10/10、online/match、GEM 1 / VLAN 1000、VLAN 存在、目标无 WAN/业务端口、全局 298 严格 ABSENT。保存批次及单动作意图后，发送 298 创建命令一次。
2. 设备回到正常提示符，无独立错误行，也没有 `Command executed successfully`。本地严格 ACK 检查因此暂停，没有重发，也没有继续盲下发。独立按 298 读取完整详情得到 FOUND / up，精确核对目标、VLAN/user-VLAN 1000、GEM 1、translate，证明本次创建已生效；这不是“端口创建失败”。原停止记录保留，不改成显式 ACK 成功。
3. 在原批准范围内另存继续意图，只执行未尝试的 IPoE index 1 一次。该命令同样静默返回，严格 ACK 检查暂停；独立查询确认目标出现唯一 DHCP/IPoE VLAN 1000 WAN，起初 Connecting，之后取得 192.168.87.19 / 网关 192.168.87.1。没有重发 IPoE，也没有重建 298。
4. 再查身份、298 完整映射、唯一 IPoE 且尚无 PPPoE，保存最后一项意图，在原批准范围内只发送 PPPoE index 0 一次。随后仅只读轮询与 Web 采集，无重试、重拨、断开、删除或额外配置。
5. 初期 OLT 读值经历 PPPoE Connecting、VLAN 0 后变 1000，以及一次 IPoE 重新 Connecting。后续 Web 先显示两条 IPv4 up；没有将时间不同的读值拼成同时通过。最后另建只读连接，OLT 和 Web 都重新采集，确认同一设备两侧地址、网关、VLAN 与状态一致后，才给出下表结论。

三条设备配置命令的实际发送次数分别为 **298 创建 1 次、IPoE 1 次、PPPoE 1 次**。无自动重试/清理；每次继续依据已批准且尚未尝试的动作与新的确定读回，不重复不确定写入。未修改现有 Runner 的强 ACK 门禁或自动资源归属逻辑。

### 最终实测结果

| 项目 | OLT | ONU Web / 实截屏 | 本次结论 |
|---|---|---|---|
| 目标注册 | 0/2/9:19，Profile 10/10，online / match | 当前 SN 与 OLT 一致 | 身份/在线确认 |
| 业务端口 | 298，up，GEM 1，VLAN/user-VLAN 1000，translate | 两条 WAN 相同 VLAN | 映射创建读回确认 |
| IPoE IPv4 | CONNECTED，192.168.87.19，网关 192.168.87.1，VLAN 1000 | nas0_0，INTERNET，up，相同地址/网关 | IPv4 建链 PASS |
| PPPoE IPv4 | CONNECTED，10.11.20.117，网关 10.11.20.1，VLAN 1000 | ppp0_nas0_1，TR069，up，相同地址/网关 | IPv4 建链 PASS |
| PON | 注册 online / match | O5，ONU ID 19 | O5 确认 |
| 光功率 | 未读取 OLT 光功率 | Rx -13.925450 dBm，Tx 2.435350 dBm | 仅记录，不作阈值判定 |
| 配置/LOID | Config state=failed | LOID Error | 原因未定，未修复，未转为已接受豁免 |

OLT 本轮显示的 WAN Index 是 IPoE 1 / PPPoE 2，而下发 ip-index 为 IPoE 1 / PPPoE 0；仅记录设备实际显示，不推断两套编号的通用映射。PPPoE 服务类型 TR069 不证明 ACS 测试通过。

IPv6 不在本轮验收结论内：最终截图中 IPoE IPv6 up、有地址，PPPoE IPv6 down；不将 IPv4 建链 PASS 写成 IPv6 或全业务 PASS。本轮未执行 Ping、LAN 绑定/NAT、电脑侧 DHCP/DNS/公网出口或 HTTP/HTTPS、重启恢复、ACS、吞吐或长期稳定性测试。

### 组件兼容性观测与平台边界

本次 MA5800 对创建端口和 IPconfig 的成功配置仅返回正常提示符，没有显式成功文案。当前代码的端口 ACK 门禁要求该文案，因此会安全停下；现场通过独立完整读取确定状态后，按原用户批准分阶段完成剩余人工维护动作。这是需要后续单独评审/测试的兼容性观测，不是本轮已修复的代码缺陷。没有放宽解析、修改门禁或声称整个平台能自主续跑。

操作调用现有连接、类型化命令、解析和证据组件，是一次性用户授权维护；没有创建持久化 Skill Session、OperatorInteraction 或自动 CREATED/REUSED 账本，也未创建/修改 TestRun、RunResult、平台 Evidence、Report、Archive 或数据库。不能据此把完整平台现场闭环标为已通过。业务配置保留在设备上，没有自动删除；既有授权不包含后续清理。

### 证据目录与核验

全部位于已忽略的 `data/local-runner/`，四阶段互不覆盖，共 97 个文件：

- `dual-wan-execute-20261015/40bd53c2d9e84ab08218eb7e921b0f57/`：28 个，写入前快照/意图、298 创建静默回执、停止记录及精确读回。
- `dual-wan-continue-20261015/04413009d5c5445eb9f08a2630c37c5b/`：20 个，原授权继续意图、IPoE 单次下发、停止记录和 WAN 读回。
- `dual-wan-final-20261015/68f28907c97a4c8ab6fec290b652036b/`：35 个，PPPoE 单次下发、早期状态轮询、首次双 WAN Web 实截图及当时 OLT 尚未一致的摘要。
- `dual-wan-verify-20261015/9fd0e48a82914f93b49e21480b768a4a/`：14 个，最终独立只读 OLT/Web 一致性核验、298/PON、最终摘要与真实 WAN/PON 截图。

每阶段生成时逐项核验大小和 SHA256，检查当前 OS 凭据不出现在证据文本；账号密码未写入脚本、配置、文档或提交集。最终 WAN/PON 真实截图均已目视核对。

| 最终证据（位于最后一目录） | SHA256 |
|---|---|
| verified-summary.txt | 41787909a7e6575b4cfab9dab59773409792d2424ec0317e889fa4125b37c713 |
| web-wan.png | cff7ce7f6f0e57bb1fd89a0ea3857e5929a1954ed6570f04cd3f5cf193369102 |
| pon.png | 2ca0e7766f50d23d7ef44f917a6dee94dbd2e070f44bf1b249c5d9402f8d63cd |

SSH/浏览器资源均已关闭。共享 Profile、LAN/NAT、电脑网卡/路由未修改；业务代码/依赖未改，本轮未重复跑全量软件测试。只追加两份现场文档，未提交/推送，main 不变。建议下一步以各自实际 WAN 接口进行网关、公网 IP、域名的分层 Ping；未经新指令不继续扩大测试或设备写入。

## 双 WAN 显式接口分层 Ping（2026-10-15）：6/6 PASS

用户要求“下一步”，按上一阶段建议执行网关、公网 IP、域名的 ONU 内置 IPv4 Ping，不包含设备配置变更。实时 Web 完整 SN 还原原批准目标预览 hash 一致，配置绑定不变；两条现有 WAN 的 VLAN、状态、接口名称、地址与各自网关重新核对。本次不调用电脑 Ping，不借用电脑其他网卡出口作为 ONU 证据。

### 绑定与判定规则

- WAN 状态接口 IPoE=nas0_0、PPPoE=ppp0_nas0_1；诊断下拉框真实名称为 nas0_0 / ppp0，内部 value 分别为 130816 / 65537。Any 的 value=65535，明确排除。每次从实际选项建立名称/值映射，验证执行前后唯一选中项和值一致，不把内部数字直接当作接口名称。
- 每项发送 4 包。本固件没有包数输入项，按已有组件验证过的固定 4 包读取，不等待虚构第 5 包。
- 保持现有 run_ping 导航/旧结果清除防护；另核验返回文本 PING 目标头、4 包统计与接口选中项，避免把前一次结果判为本轮。
- 通过条件：4/4、丢包 0%、平均 RTT 有值且小于 100 ms；不只依赖原 parser 的零丢包状态。域名项只说明 ONU 的本次域名解析及 ICMP 可达，不证明 LAN DNS Proxy 或电脑 DNS 可用。

### 实测结果

| WAN / 诊断接口 | 目标 | 发/收 | 丢包 | 平均 RTT(ms) | 结果 |
|---|---|---|---|---:|---|
| IPoE / nas0_0 | 192.168.87.1（当前网关） | 4/4 | 0% | 2.090 | PASS |
| IPoE / nas0_0 | 1.1.1.1 | 4/4 | 0% | 53.636 | PASS |
| IPoE / nas0_0 | www.baidu.com | 4/4 | 0% | 9.639 | PASS |
| PPPoE / ppp0 | 10.11.20.1（当前网关） | 4/4 | 0% | 1.789 | PASS |
| PPPoE / ppp0 | 1.1.1.1 | 4/4 | 0% | 53.959 | PASS |
| PPPoE / ppp0 | www.baidu.com | 4/4 | 0% | 9.862 | PASS |

这六项各有一次完整有效结果，并非同时进行的长时间稳定性测量。没有重测已通过的首项来替换结果，也没有把前置阻塞误判为网络 FAIL。

### 临时调用问题与保留的失败过程

1. 第一批临时调用错误要求 select 的 value 等于 nas0_0/ppp0，实际是数字编码；六项均在 Ping 提交前被挡住。随后只读检查原始选项，确认正式选择策略已选对接口，错误在临时调用的额外断言，不是设备断网。未改现有选择器或放宽到 Any。
2. 该批临时失败证据的 `*-blocked.png` 既用于文本渲染又用于浏览器截图，同名覆盖导致文件与先前返回的 ArtifactPayload hash 不一致，脚本最终 exit 1。原目录 `data/local-runner/dual-wan-ping-20261015/81612972eb554c04b03b43d91a28471a/` 保留，不声明整体 Hash 验证成功，不作为实际 Ping 验收依据。原文本保留；后续改为新的独立目录、`*-browser.png` 与不重复命名，并检查路径唯一，不覆写历史文件。
3. 第二批用真实名称/值校验后，IPoE 网关成功；随后临时跨六项复用同一浏览器，旧结果子框架在重新导航时 detached，run_ping 的提交前 body 快照异常，剩余五项 BLOCKED。保留当时 1 PASS / 5 BLOCKED 的摘要，不伪造其为 6 PASS。
4. 对照正式 NeutralONUWebAdapter 每次新建/关闭 surface 的调用方式后，采用相同生命周期逐项完成尚未通过的五项。没有修改 NeutralPlaywrightSurface、run_ping 的缓存/导航保护或平台业务代码。后续五项均取得对应目标的新鲜完整结果。该处理不等于已修复所有 iframe 兼容问题或平台整链路已验收。

### 最终证据与边界

有效结果来源及过程证据均被 Git 忽略：

- `data/local-runner/dual-wan-ping-verified-20261015/d8e5d07e54e949f5a7abe1d2d9a96ff9/`：34 个唯一文件，含首个网关 PASS 和后续框架阻塞记录；大小/SHA256及凭据文本检查通过。
- `data/local-runner/dual-wan-ping-isolated-20261015/7c643eed648543f28776f5d87242263b/`：29 个唯一文件，含其余五项原文、统计、真实截图及引用首个网关来源的最终 6/6 汇总；大小/SHA256及凭据文本检查通过。

最终汇总不隐藏前两阶段失败，并引用首项原证据目录。两条 WAN 的域名 Ping 实截屏已目视确认所选接口、目标、4 包统计和延迟，没有用文本渲染图冒充浏览器截图。

| 关键证据 | SHA256 |
|---|---|
| verified 目录 / ipoe-gateway-raw.txt | d472729e7824ef20aa56d65614d07c107f0cc02a24183e14a00e7d030ce71b38 |
| isolated 目录 / diagnostic-final-summary.txt | ecd75151e890759dfacb7ff561b81fca4b1ce66a68be704a6277131fbaaf9d1f |
| isolated 目录 / ipoe-domain-browser.png | 7e1437cb78a57b6688b6482f9b4c404f8995d7204f3e23dea1a1c089aa2b87ba |
| isolated 目录 / pppoe-domain-browser.png | bc71a33e6420421e6471576fc7d5ba1da89f58e28e892aee887d1ca554b63af9 |

本次仅证明 ONU 内置诊断经指定 WAN 到达上述 IPv4 目标。未验收电脑侧 LAN/NAT/DNS/HTTP、IPv6、ACS、吞吐、重连或长稳；此前 Config failed / LOID Error 仍保留，未证明修复。未操作 OLT 配置、WAN 开关、共享 Profile、电脑网卡/路由或数据库；未创建 Run、Result、Session、平台 Evidence/Report/Archive。浏览器均关闭。

仅两份现场文档更新，未提交/推送，main 不变；无业务代码改动，本轮未重复跑全量单元测试。下一步应整理组件验收与平台执行闭环的差距，单独评审既有执行器兼容问题，不凭这次临时组件测试宣布 Skill 自主执行完成，也不扩展 LAN/NAT 等其他 Skill 范围。

## MA5800 空列表与静默创建回执兼容修复（2026-10-16）：离线验证通过

本节为用户批准后的软件修复验证，不是新的现场操作。此前各轮设备记录原样保留；本轮未连接设备、未操作凭据、未修改平台数据库或创建 Run/Result/Session。

### 修复范围与安全边界

- 仅对完整且命令目标 FSP/ONT 一致的 `Failure: No service virtual port can be operated` 响应识别为空服务端口列表；其他错误、目标不符、混杂内容、截断或缺少最终提示符继续阻塞。通用命令失败解析不放宽。
- 仅对与本次 CREATE 命令严格匹配的已采样静默回显识别“命令交互完成”。显式 ACK、交互完成和独立读回证明分开记录，静默回执本身不能判成功。
- 执行器在既有有效审批、持久化意图及最新 ABSENT 检查后，最多发送一次创建命令；随后独立完整读回，核对端口 ID、FSP/ONT、SN、Profile、GEM/VLAN 等既有约束。只有读回吻合且证据持久化，才可形成已验证创建及资源归属。
- 超时、未知内容、明确错误、缺失或不匹配的读回仍为阻塞/不确定；不自动重放，不自动清理。删除逻辑、WAN 下发语义、Snapshot/LOCKED、数据库设计、API 和前端均未调整。

### 测试先行与完整验证

修改范围为 `ma5800/parsers.py`、`ma5800/actions.py`、`local_runner/runtime.py` 及两份关联测试。相关基线 63 项通过；新增测试先出现 3 项预期失败，首次实现后仍有 1 项失败，定位到快照上层的通用失败判断并完成同范围修复；最终定向回归 **85 passed**，未用放宽通用解析替代目标校验。

2026-10-16 完整验证：

| 验证 | 结果 |
|---|---|
| 后端 `python -m pytest backend/tests -q`（隔离 venv、新建短临时路径） | 868 passed，2 warnings，487.80 秒，退出 0 |
| 前端 `npm.cmd test -- --reporter=dot --maxWorkers=1` | 26 个文件，62 passed，81.95 秒 |
| 生产构建 `npm.cmd run build` | TypeScript 与 Vite 构建通过 |

两项后端告警为未知 `asyncio_default_fixture_loop_scope` 配置和 Starlette TestClient/httpx 弃用提示，未修改依赖。默认临时目录权限及过长临时路径问题通过本次测试调用使用新建短路径避开；一次 JUnit 参数调用错误未执行测试，不作为通过依据。

有效全量日志位于被 Git 忽略的 `data/validation/ma5800-compat-20261016-1792120685063/backend-tests-rerun.txt` 与 `backend.junit.xml`；前端测试/构建日志位于同级 `ma5800-compat-20261016-1792120685063-frontend/`。独立只读代码审核未发现 Critical/Important 问题；显式三种事实断言以及更多 SN/Profile 等漂移组合测试是非阻塞加固建议，未扩展本轮修改。

### 当前结论

离线兼容修复及全量软件回归通过；**平台持久化真机全流程仍为 NOT_EXECUTED**。下一步应先核对现有运行配置、审批与目标绑定，再单独安排平台端到端验收；不得将此前人工组件测试或本次模拟测试写成平台自主执行通过。现有两份现场文档保留全部历史，本轮修复与文档尚未提交、合并或推送，main 保持不变。
