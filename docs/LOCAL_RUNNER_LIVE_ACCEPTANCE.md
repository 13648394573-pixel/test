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
