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
