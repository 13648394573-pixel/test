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
