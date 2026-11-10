# Test Workbench 项目进度

## 最新核对：2026-10-15（离线准备）

本节优先说明当前状态；下文 2026-10-10 内容保留为历史，不代表当前功能分支已合并。

- main：`0e915f22d9bc1caf6c4cfa22b665a35b5312f3f1`，本次检查干净、未修改。
- 自动化开发分支：`codex/skill-execution`，`ea2d91d6d8d1ef52567210d53e3560493859f23e`。Task 1–7 软件交付已有提交；当前版本未合并 main，本次不推送。
- 已实现：本机配置/凭据引用绑定、保留注册的 v2 执行计划、端口映射契约、追加式归属账本、审批创建、核验后清理、中断只读核对、既有测试执行页的审批与独立清理入口。
- 最近代码提交前验证：后端 846 passed（487.39s）、前端 62 passed（80.16s）、生产构建通过；这是该次代码验证记录，本次仅文档准备，没有重跑全量回归。
- 2026-10-12 已有真实组件验证证明 OLT 注册、online/match、ONU O5、光功率采集、IPoE/PPPoE 建链及各接口分层 Ping；不是新端口生命周期的实际平台会话验收，不能混同。
- 尚未完成：当前版本的现场平台复用/创建/清理验收。完整 WAN 自动恢复仍不支持；LAN 绑定/NAT 功能测试留给独立 Skill。当前审批界面需要输入已有 session_id，不是完整一键启动向导。
- 本次离线检查发现：主目录配置合法但缺少 service_port_profiles；功能分支默认配置不存在，当前进程未指定配置路径；系统 Python 有 4 项依赖不符合 backend/pyproject.toml。未修配置、升级依赖或读取凭据值。

下一步先解决本机运行准备差异，再在设备可用并重新核对目标后做只读复用验收。具体清单、实际检查结果和停止条件见 [离线准备与现场验收清单](LOCAL_RUNNER_OFFLINE_READINESS.md)。不因历史 ONT ID、端口编号或样例数值而授权现场写入。

### 隔离环境准备追加（2026-10-15）

已在功能分支忽略目录 .venv 创建 Python 3.12.5 环境，按现有 backend[dev] 声明安装；全部直接依赖/dev 约束符合，pip check 通过，没有改变系统 Python 或 pyproject.toml。
新环境全量后端实测为 **835 passed / 1 failed / 10 errors（470.33s）**，不能沿用原环境 846 passed 作为新环境通过结论。10 项错误为缺少当前 Playwright 对应的 Chromium headless shell；下载缓慢，本轮主动停止，未补齐。
另 1 项失败已最小复现：既有指纹核对测试的 Transport 替身缺少 Paramiko 3.5.1 调用的 set_gss_host；本轮未修改测试或生产逻辑，不把它认定为真实 SSH 连接失败。后续先单独确认测试兼容性修正与浏览器补齐，再复验；不使用声明范围外的 Paramiko 5 绕过。
状态：隔离环境已创建，依赖安装合规，运行验收 **HOLD**。未连接设备、启动应用或迁移现场数据库，未提交/推送文档。

### 已批准的兼容性收尾（2026-10-15）

用户同意继续后，仅修正现有 SSH 安全测试的 Transport 替身：补齐关闭 GSS 场景接口，错误指纹分支改为要求明确 HostKeyFingerprintMismatchError，不再接受任意异常；生产连接器不改。定向验证为 RED 2 failed → GREEN 2 passed（1.13s）。
新版 Chromium 下载仍慢，已停止；隔离环境改用项目声明允许、此前已验证且本机有配套浏览器的 Playwright 1.61.0，未改 pyproject.toml。实际无头浏览器启动/内存页面渲染通过，相关离线页面/脱敏/Ping/SSH 测试 36 passed（16.49s）。依赖约束及 pip check 均通过，不把浏览器可执行文件存在当作启动成功证据。
最终隔离后端全量回归：**846 passed、2 warnings（446.89s），exit 0**；此前 1 failed / 10 errors 已无复现，旧 HOLD 记录保留为历史。两条警告为既有异步测试配置项未知和 Starlette/httpx 弃用提示，未在本轮扩展修复。隔离离线运行门禁 PASS；现场目标配置和验收仍未就绪，不等同于整个平台或现场闭环 PASS。本轮 1 个测试文件及 2 份文档未提交/推送，main 未修改。

### 前次登录预检：BLOCKED（2026-10-15，随后解决登录）

已固化基线为 codex/skill-execution / ed9f33e5b35dde8faba94dc4f24145118442769a。用户确认设备连接后，仅进行只读预检：测试网卡在线，OLT 管理端口 TCP 可达；当前 ONU Web 返回 `ERROR: invalid username!`，无法读取实时 SN。
早期组件未抛异常的返回曾被误记为登录成功；实际响应证明认证未成功，现已更正并停止重试。未使用旧 SN/ONT ID，未建立 OLT 认证会话或查询注册/Profile/端口；未创建 Run、访问数据库或写设备配置。
现场状态 BLOCKED，需先确认当前 ONU Web 账号并通过隐藏输入重新登记。另发现组件对该错误响应的登录成功判定不足，已记录，未在本次只读任务中修业务代码。详情及脱敏证据见 LOCAL_RUNNER_LIVE_ACCEPTANCE.md 的本次追加。

### 当前只读补验：BLOCKED，注册位置不一致（2026-10-15）

用户提供并确认新的 ONU 凭据格式后，通过隐藏输入仅更新本机 OS 凭据库中的 ONU 访问对；没有凭据值进入脚本、文档或设备配置。Web 实际登录及当前 SN 读取成功（仅保留尾号 CD73），并在已固定 SSH 指纹校验下匹配 OLT 记录。
旧注册为 0/2/2:2，Profile 10/10，offline、Config/Match initial；当前同一 SN 在 0/2/9 自动发现，Equipment ID 为 BT-G711AX。ONU 实际 Status/PON 页面为 O2、Rx -14.089354 dBm、Tx 2.208155 dBm，未达到 O5。旧位置已有 service-port 298（VLAN 1000/GEM 1/user VLAN 1000），非本次创建，不自动认领或清理。
只读采集完成不等于产品 PASS。当前阻塞是实际接入口与旧注册位置不一致；WAN 未取得可判定条目，不能写成 IPoE/PPPoE 通过或断言 WAN 未配置。已保存 17 个本地脱敏证据文件并检查 hash，包括真实 PON 页截图。未创建平台会话、打开数据库、注册、下发 WAN、删除端口或改业务代码。
下一步由用户选择：将光纤接回已注册的 0/2/2 后重新只读验证，或明确授权先规划迁移到 0/2/9。迁移涉及旧注册/端口，必须另核对备份与变更范围，不因本次只读授权而执行删除。原登录误判覆盖缺口保留，未修复。本轮两份现场记录未提交/推送。

### 当前状态：旧注册清理完成，0/2/9 待注册（2026-10-15）

用户选择保留当前 0/2/9，并明确将删除业务端口命令改为 `undo service-port port 0/2/2 ont 2`、同意其余旧注册删除步骤。执行前重新读取当前 Web SN，核对尾号 CD73 对应旧 0/2/2:2、offline、Profile 10/10，关联端口仅 298 且 down；保存脱敏前置快照。
已执行用户指定命令，OLT 回执删除 1 条业务端口；独立全局查询确认 298 不存在。随后仅执行 `ont delete 2 2`，OLT 回执 1 success，并按当前 SN 查询确认 `The required ONT does not exist`。没有重试删除，没有新注册、WAN 下发、共享 Profile 修改或数据库写入。
本次为用户指定的一次性现场维护，不冒充平台自动清理，不将旧端口认领为 CREATED。32 个本地审计文件已保存/核验；前置快照可供人工重建参考，不承诺完整自动恢复。发现两种固件缺失响应与现有严格解析不一致，均保留真实输出，未修生产代码。
下一步先只读核对 0/2/9 的实时发现、空闲 ONT ID 及 Profile，再明确新注册范围；本次没有沿用旧 ONT ID 或执行新注册。两份现场文档未提交/推送，main 未修改。

### 当前待确认：新口注册预览（2026-10-15）

只读重查当前 Web SN（尾号 CD73），OLT 明确未注册，唯一匹配的自动发现位置为 0/2/9，Equipment ID BT-G711AX。完整占用列表共 21 个 ONT，与返回总数一致；已占用 0–18、100、101，候选 ID 19 当前空闲。Profile 10/10 现场读取确认，GEM 1 包含 VLAN 1000。
已生成注册预览：0/2/9:19、当前 SN、sn-auth、OMCI、Line/Service Profile 10/10；hash 为 53e65724d3abf3d66efe42734b7b15e838c0b8ecc752260563d4d39e93ebfaaf。尚未执行 ont add、不创建业务端口、不下发 WAN。保存 12 个本地证据文件并核对 hash，等待用户确认这项新注册；执行前须再次读取身份/自动发现/ID 占用，变化则停止。

### 最新现场状态：新口注册成功，online / match / O5 已确认（2026-10-15）

用户明确确认上述注册预览后，重新从 Web 读取完整 SN，用它还原预览的 canonical JSON 并核对原预览 hash 一致；配置绑定 hash 不变。再查旧注册不存在、同一 SN 唯一发现于 0/2/9、ONT 19 空闲及 Profile 10/10 有效，保存本地写入意图后，只执行一次 `ont add 9 19`（SN 认证、OMCI、Profile 10/10）。OLT 明确返回可添加 1、成功 1，PortID 9 / ONTID 19。

注册后有界只读轮询：前两次 offline / initial / initial，第三次 online / failed / match；完整 SN、0/2/9:19 和 Profile 10/10 均匹配。真实 Status → PON 截图确认 ONU State O5、ONU ID 19，Rx -13.936186 dBm、Tx 2.449209 dBm；仍显示 LOID Error。Config state=failed 和 LOID Error 作为待分析观测保留，不直接套用历史设备的豁免，也不声称配置全部正常或双 WAN 测试通过。

证据保存在已忽略的 `data/local-runner/register-execute-20261015/a7a705574ad747eeb013fdbbcedfd16f/`，共 25 个文件，大小/SHA256 全部核对，凭据文本泄漏检查通过，PON 真实截图已目视核对。本轮未创建 service-port、未下发 IPoE/PPPoE、未操作平台数据库/历史 Run；只追加两份现场文档，未提交/推送，main 不变。下一步先只读定位配置失败，再对业务端口/WAN 给出独立变更预览，未经批准不写入。

### 配置失败只读排查（2026-10-15）：原因未确定，WAN 尚未下发

重新核对完整身份与已批准预览 hash 一致，当前仍为 0/2/9:19、Profile 10/10、online / failed / match，PON 为 O5、ONU ID 19，LOID Error 仍在。OLT 的 WAN 查询明确返回 `WAN port does not exist`，该 ONT 的 service-port 查询明确返回 `Failure: No service virtual port can be operated`。这些读值确认本轮尚无 WAN/业务端口，符合此前没有下发的边界；不能据此认定 Config failed 的根因是“缺少 WAN”，也不能判定 ONU 固件异常。

尝试只读 `display ont failed-configuration 9 19`，设备返回 Unknown command。读取当前 GPON 接口视图及 config 视图的 `display ont ?` 帮助，均未列出该失败配置查询；清除待输入命令并正常退出，没有进入 diagnose 模式、反复猜命令或试写 Profile/认证方式。现有注册详情也未提供具体配置失败原因，因此该原因本轮仍为 UNDETERMINED。

本地证据目录 `data/local-runner/config-failure-readonly-20261015/5200890ba66f4f0abde23169bf191f55/`，19 个脱敏文本/渲染图及真实 PON 截图，两个采集阶段分别校验大小与 hash，凭据文本检查通过。设备配置写入 0，未打开数据库，未修改代码；两份现场文档未提交/推送，main 不变。后续应把业务端口/IPoE/PPPoE 作为独立授权测试，不将业务下发当作已证实的配置失败修复；LAN 绑定/NAT 继续留给其他功能测试。

### 双 WAN 只读预览（2026-10-15）：待批准，未执行

实时 Web 完整 SN 与原注册预览 hash 再次核对一致；0/2/9:19 保持 online / failed / match、Profile 10/10。重新确认目标无 WAN/业务端口，Line Profile 10 含 GEM 1 / VLAN 1000，VLAN 1000 存在。全局严格详情查询确认候选业务端口 **298 为 ABSENT**，不是根据旧删除记录推断空闲。

待批准的人工维护范围：在 0/2/9:19 新建 298（VLAN/user-VLAN 1000、GEM 1、translate），IPoE 与 PPPoE 映射相同，共享这一个端口；下发 IPoE ip-index 1 DHCP、PPPoE ip-index 0，使用已登记 OS 凭据。未执行上述任何写入，不涉及 LAN 绑定/NAT、共享 Profile、旧资源删除、重启或平台数据库。Config failed / LOID Error 根因仍未确定，本预览不作为其已确认修复。

预览 hash：`7bc1667955221fdc1df90ea472d3d553c438cd7b3eb0826ac6b21d7f49ac85ec`。14 个核验过大小/SHA256及凭据脱敏的文件位于已忽略目录 `data/local-runner/dual-wan-preview-20261015/f7c29c7f9cd44dbc9fac545d0079f565/`。执行前需再核对身份/占用/业务状态；状态变化则停止，无自动重试/清理。两份文档未提交/推送，main 不变。

### 最新现场结果：批准后的双 WAN IPv4 建链通过（2026-10-15）

用户明确批准预览 `7bc1667955221fdc1df90ea472d3d553c438cd7b3eb0826ac6b21d7f49ac85ec`。写入前重验完整 SN/绑定/0/2/9:19、Profile/GEM/VLAN、目标无 WAN/端口及 298 全局空闲；各阶段先存本地意图。实际新建 298、下发 IPoE index 1 和 PPPoE index 0 各一次，未重试或自动删除。命令返回提示符但无显式成功文案，严格回执检查先暂停；独立完整读取确认 298 已按目标映射创建、再确认 IPoE 已产生后，才在原授权内继续尚未尝试的下一动作。保留暂停记录，不伪造显式 ACK 或修改生产门禁。

最终独立只读交叉核验：298 up，目标 0/2/9:19、GEM 1、VLAN/user VLAN 1000、translate；OLT/Web 两侧 IPoE 为 CONNECTED/up、192.168.87.19、网关 192.168.87.1；PPPoE 为 CONNECTED/up、10.11.20.117、网关 10.11.20.1，均 VLAN 1000。Web 接口分别 nas0_0 / ppp0_nas0_1，服务类型 INTERNET / TR069。OLT 本轮显示 Index 1/2，不与命令 ip-index 1/0 混同。早期 OLT Connecting 与稍后 Web up 的时间差保留，最终重新查询才判 IPv4 建链通过。

ONU 保持 online / match、O5、ID 19；Config failed / LOID Error 仍在，不能称已修复。IPv6 未验收（截图 PPPoE IPv6 down），Ping、LAN 绑定/NAT、电脑上网、ACS/长期稳定性均未验收。本次是人工授权调用现有组件，不等于平台持久化 Skill 全流程通过；静默成功回执与当前 ACK 门禁的兼容问题待另行处理，未改代码。

四阶段本地证据共 97 文件，分别位于 `data/local-runner/dual-wan-execute-20261015/40bd53c2d9e84ab08218eb7e921b0f57/`（28）、`dual-wan-continue-20261015/04413009d5c5445eb9f08a2630c37c5b/`（20）、`dual-wan-final-20261015/68f28907c97a4c8ab6fec290b652036b/`（35）、`dual-wan-verify-20261015/9fd0e48a82914f93b49e21480b768a4a/`（14），后面三个目录同属 `data/local-runner/`。生成时校验大小/Hash和凭据脱敏；最终 WAN/PON 实截图已核对。未操作平台数据库/历史 Run、共享 Profile、LAN/NAT 或 Git main；仅两份现场文档更新，未提交/推送。下一步建议按每条 WAN 明确绑定接口执行网关/公网 IP/域名 Ping，不能用建链结果代替连通性。

### 最新现场结果：双 WAN 分层 IPv4 Ping 6/6 通过（2026-10-15）

实时 Web 完整 SN/配置 hash 与既有目标一致，两条 WAN up、VLAN 1000，按各自当前网关测试。IPoE 明确选择诊断接口 nas0_0（内部 value=130816），PPPoE 选择 ppp0（value=65537），前后均核对唯一选中名称和值，未使用 Any。调用现有 run_ping 的旧结果防护、核验当前目标头和 4 包统计；全部 4 发 4 收、零丢包，平均 RTT 均小于 100 ms。

| 接口 | 网关平均 RTT(ms) | 1.1.1.1 平均 RTT(ms) | www.baidu.com 平均 RTT(ms) |
|---|---:|---:|---:|
| IPoE nas0_0 | 2.090 | 53.636 | 9.639 |
| PPPoE ppp0 | 1.789 | 53.959 | 9.862 |

临时调用先因把数字 option value 误当接口名称而预检阻塞，未发包；随后复用浏览器在首个网关通过后触发旧子框架 detached，保留该通过项，按正式适配器每次新建浏览器方式完成其余五项。没有修改业务代码、接口选择策略或新鲜结果门禁。最初临时失败采集还发生渲染图/截图同名覆盖，导致该批整体 Hash 检查未通过，原样保留且不作为验收依据；后续使用独立目录和不重复文件名。

最终六项依据分别在已忽略的 `data/local-runner/dual-wan-ping-verified-20261015/d8e5d07e54e949f5a7abe1d2d9a96ff9/`（首项有效结果及阻塞过程，34 文件已核验）与 `dual-wan-ping-isolated-20261015/7c643eed648543f28776f5d87242263b/`（其余五项及最终汇总，29 文件已核验，同属 data/local-runner）。每项有脱敏文本、统计及真实截图，最终域名截图已目视核对；凭据文本检查通过。

结论仅为当前 ONU 内置诊断的显式 WAN 绑定 IPv4 连通性，不替代电脑侧 DNS/NAT/HTTP、IPv6、ACS 或稳定性验收；Config failed / LOID Error 未修复。本轮没有设备配置/电脑网络/数据库/业务代码变更，仅两份现场文档更新，未提交/推送，main 不变。下一步聚焦既有执行器兼容性及平台持久化执行闭环准备，不擅自扩展到其他功能 Skill。

### 最新软件结果：MA5800 受限兼容修复离线通过（2026-10-16）

用户批准后，仅修改本地执行器的 3 个生产文件和 2 个测试文件：精确识别目标作用域内的已采样空服务端口响应；允许严格匹配的静默 CREATE 回执进入独立完整读回，不把无错误/回到提示符当作成功。显式 ACK、交互完成与读回成功分开记录；审批、意图、最新 ABSENT、目标身份/映射及持久化证据仍是成功与资源归属的前提。未知、超时、错误或读回不符继续阻塞，不自动重放或清理。

测试先行：原相关基线 63 passed；新增测试先出现 3 项预期失败，修复后定向 85 passed。新鲜全量验证：**后端 868 passed / 2 warnings（487.80 秒），前端 62 passed / 26 文件，生产构建 PASS**。两项后端告警为现有 pytest 配置及 Starlette/httpx 弃用提示，本轮不变更依赖。独立只读审核无阻塞发现；更多事实断言/漂移组合测试作为非阻塞加固建议保留。

有效日志位于已忽略的 `data/validation/ma5800-compat-20261016-1792120685063/`（后端以 `backend-tests-rerun.txt` 和 `backend.junit.xml` 为准）及同级后缀 `-frontend/` 目录。Windows 测试临时目录采用新建短路径；失败的环境/参数调用记录不计作通过结果。

本轮未操作真实设备、凭据或平台数据库；未改删除逻辑、WAN 语义、Snapshot/LOCKED、数据库结构、API 或前端。隔离分支 `codex/skill-execution` 基线仍为 `ed9f33e5b35dde8faba94dc4f24145118442769a`，修复与两份文档尚未提交/合并/推送；main 工作区干净且基线未变。**下一步为平台执行闭环验收准备，不是宣布真机 Skill 已完成**：既有现场组件结果有效，但平台授权→执行→证据→归属的持久化全流程仍未实测。

## 历史进度记录（2026-10-10）

更新：2026-10-10。修复前基线：main / 7107c8e；现场适配修复随本轮记录固化。

## 已交付

| 阶段 | 主线能力 | 核对依据 |
|---|---|---|
| V1 Sprint 0–7 | 设备、用例、Run、结果锁定、证据、缺陷/回归、环境快照、报告/归档 | V1 发布记录、v1.0.0 标签 |
| V1.1 Sprint 8–10 | Diagnostic、Focused Regression、历史筛选/比较、Evidence 效率改进 | 2606cf3、11846ce、4633368 |
| V2 Sprint 0 | Standard、Skill、模板、执行快照、Runner 注册、事件与恢复基础 | [验收记录](V2_SPRINT0_FOUNDATION_VERIFICATION.md) |
| ONU 注册与双 WAN 基础 | DRAFT Skill、凭据、MA5800 parser/transport、受控动作、ONU WAN/Ping、PC 连通性采集 | 主计划 Task 1–7 提交 206ecf2 至 b98ade9 |
| 现场兼容性检查 | 只读 OLT/ONU 探测、编排、报告、本机 API、中文向导 | 0c1afe7 至 baae7b2；[说明](ONU_LAB_COMPATIBILITY_CHECK.md) |

最终目标为本地自动化测试工作台。V1.0.0 提供测试管理闭环，main 继续推进自动化。后续代码不等于新版本已发布，也不表示现场验收已通过。现场检查返回 READY/PARTIAL/BLOCKED，不作为产品 PASS/FAIL，不创建正式 TestRun。

## 下一步

1. 真实 MA5800-X7 / ONU 只读兼容性检查已完成；IPoE/PPPoE 状态读取及各自接口 Ping 已通过固化后的适配器验证。见[现场适配记录](ONU_VERIFIED_ADAPTER.md)。本轮同时修复旧 Ping 结果误判及缓存文本脱敏遗漏；这不等于正式 Skill 全流程验收完成。
2. 核对并完成[正式 Skill 计划](superpowers/plans/2026-09-18-onu-registration-dual-wan-skill.md) Task 8–12：可恢复执行/判定、执行 API、向导、离线启动/报告、真实验收。
3. 验证注册、双 WAN、ONU/PC 连通性和证据链可重复执行，完成发布回归、迁移及恢复检查。

## 旧分支与验证边界

feature/onu-automation-engine 位于 131b119，Task 4 尚有五个未提交修复文件，未完成最终验证与整合。本次保留旧 worktree 原状；恢复前须与 main 的 local_runner/lab_compatibility 比较覆盖范围，避免重复实现。

V2 Sprint 0 曾记录后端 244 passed、前端 48 passed；旧 Live Runner 曾记录后端 477 passed、1 skipped。它们属于不同基线，不能作为当前 main 的验证数字。本轮真实 DUT 的 WAN/Ping 验证与全量回归结果单独记录在现场适配文档中。

本地保留 v1.0.0 与 v1.0.0-rc1。历史规划与未勾选步骤不单独代表当前进度；以主线代码、提交及验收记录共同判断。
