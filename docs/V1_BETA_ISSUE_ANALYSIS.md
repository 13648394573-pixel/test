# BETA-ISSUE-001 深度分析

## 1. 分析概览

| 项目 | 当前值 |
|---|---|
| Issue ID | `BETA-ISSUE-001` |
| 当前状态 | `OPEN` |
| 严重级别 | P1（Beta验收阻塞；尚未确认是Test Workbench代码问题） |
| Release状态 | `HOLD` |
| 分析基线 | `main` / `c84b4dd12b8aa721433fbb243a84134be85654f8` |
| 首次发现 | 2026-07-30，Round 1 |
| 最近复现 | 2026-08-03，Round 4 |
| 影响范围 | ONU online/O5、IPoE、PPPoE及网络连通正向验收 |

当前证据持续指向DUT、PON光链路或OLT侧接入条件。Test Workbench的数据记录与完整性链路已通过验证，暂无证据表明该问题由Workbench业务代码导致。最终根因必须通过现场逐项排查确认，不能仅根据`LOSi/LOBi`直接定责。

## 2. 问题现象时间线

| 轮次 | 日期 | ONU Web | OLT状态 | Test Workbench处理 | 结论 |
|---|---|---|---|---|---|
| Round 1 | 2026-07-30 | 不可达 | F/S/P `0/2/10`、ONT ID `36`；Run `offline`；Config/Match `initial`；`LOSi/LOBi` | 创建2个Run；PON/WAN为BLOCKED；生成`RPT-000001`、`ARC-000001`及首条BLOCKED Regression | 首次确认阻塞，创建`BETA-ISSUE-001` |
| Round 2 | 2026-07-31 | 不可达 | 状态与Round 1一致 | DUT未恢复，按规则未创建TestRun | 问题继续复现 |
| Round 3 | 2026-07-31 | HTTP 200，本地管理面短暂恢复 | 仍为`offline`、Config/Match `initial`、`LOSi/LOBi` | 创建独立第3个Run；1 PASS、2 BLOCKED并全部LOCKED；生成`RPT-000002`、`ARC-000002`及第2条BLOCKED Regression | 本地Web可达不代表PON恢复 |
| Round 4 | 2026-08-03 | 再次不可达 | 仍为`offline`、Config/Match `initial`、`LOSi/LOBi` | DUT未恢复，按规则未创建TestRun | 问题稳定复现，Release继续HOLD |

历史基线保持为3个TestRun、9个RunResult、2份Report、2份Archive和2条Regression。

## 3. 已确认正常项

| 检查项 | 已确认结果 | 依据 |
|---|---|---|
| OLT SSH | 正常 | Round 1–4均可连接Huawei MA5800-X7并执行只读ONT查询 |
| Workbench流程 | 正常 | Device、Case、Environment、Run、LOCKED Result、Defect、Regression、Report、Archive闭环完成 |
| Snapshot与历史数据 | 正常 | 新Run生成独立版本1 Snapshot；历史Run未被后续轮次修改 |
| Evidence | 正常 | OLT文本及渲染截图可上传、下载并纳入归档；元数据和文件路径可追溯 |
| Report | 正常 | `RPT-000001`、`RPT-000002`生成成功，HTML SHA256与元数据一致 |
| Archive | 正常 | `ARC-000001`、`ARC-000002`生成成功，ZIP SHA256与元数据一致；重复归档保护有效 |
| 结果完整性 | 正常 | 9个RunResult全部LOCKED；锁定结果修改返回409 |

## 4. 已确认异常项

| 异常项 | 当前证据 | 影响 |
|---|---|---|
| ONU offline | OLT连续查询显示Run state `offline` | 无法进入业务验证 |
| Config/Match initial | OLT连续查询显示Config state、Match state均为`initial` | OMCI配置与模板匹配未完成 |
| LOSi/LOBi | Last down cause持续为`LOSi/LOBi` | 指向光信号丢失、链路中断或DUT侧光接口条件异常 |
| 当前距离为空 | ONT distance为`-`，仅保留last distance `85 m` | OLT当前无法测得有效在线距离 |
| O5未达成 | 无online/O5原始证据 | IPoE、PPPoE及网络连通测试前置条件不成立 |
| ONU Web不稳定 | Round 3可达，Round 1/2/4不可达 | DUT供电、管理口、PC直连或软件状态需要进一步确认 |

## 5. 排查矩阵

排查必须按“物理层 → 设备状态 → 认证与模板 → OLT端口 → 业务层”顺序执行。每一步都保存原始文本或截图，未通过前不进入依赖它的后续步骤。

| 排查方向 | 当前状态 | 排查动作 | PASS标准 | 异常后的处理 |
|---|---|---|---|---|
| 光链路 | 高优先级，未确认 | 清洁并重插光纤；核对跳纤、适配器、分光器和端口；使用光功率计或替换已知正常跳纤交叉验证 | OLT检测到当前有效距离，ONT由offline转为online | 更换链路器件或端口，记录光功率与交叉验证结果 |
| ONU供电 | 未确认 | 检查电源适配器、指示灯、启动稳定性；观察重启或掉电；验证管理口持续可达 | ONU持续供电，Web和管理口稳定，无异常重启 | 更换适配器或DUT，记录供电与启动现象 |
| ONU软件版本 | 未确认 | DUT稳定后读取型号、软件/硬件版本、Vendor ID和OLT模式；核对是否支持当前OLT与OMCI模板 | 版本信息完整，OLT模式正确，版本在验证范围内 | 升级/回退到批准版本后重新建立新TestRun验证 |
| SN认证 | 部分确认 | 对比设备标签、ONU Web和OLT配置SN；检查字符、字节序和认证方式 | 三方SN一致，OLT使用SN-auth识别目标ONU | 修正OLT档案或DUT记录；禁止在未核对SN时重复注册 |
| ONT profile | 部分确认 | 核对line profile `10`、service profile `10`及实际绑定；在线后检查Match state | profile绑定正确，Config/Match正常且无不匹配告警 | 修正模板或绑定后保存变更证据，再执行新Run |
| OLT配置 | 部分确认 | 检查ONT ID `36`、F/S/P `0/2/10`、VLAN `1000`、service-port和OMCI IP host配置；确认无重复或冲突 | ONT配置唯一、参数一致、无冲突，WAN所需配置完整 | 先备份当前配置，再由授权工程师修正；记录前后差异 |
| PON端口状态 | 未确认 | 查询0/2/10端口管理/运行状态、告警、光模块状态及同端口其他ONT情况 | 端口up、无阻断告警，同端口业务状态符合预期 | 检查板卡、光模块、端口配置或切换已知正常端口交叉验证 |

### 建议排查顺序

1. 确认ONU供电和管理口持续稳定。
2. 清洁、重插或替换光纤链路，确认光功率与PON指示灯。
3. 查询PON端口状态和告警，并用已知正常ONU或端口交叉验证。
4. 核对SN、ONT ID、F/S/P及认证方式。
5. 核对line/service profile和OLT配置。
6. ONU达到online/O5后，才检查并验证IPoE、PPPoE和网络连通。

## 6. Release决策条件

### PASS条件

只有以下条件全部具备可追溯Evidence并写入新的TestRun，才能关闭`BETA-ISSUE-001`并解除Release HOLD：

- [ ] OLT显示目标ONU为`online`，F/S/P和ONT ID与预期一致。
- [ ] ONU达到O5，Config/Match状态正常。
- [ ] IPoE为Connected/up，VLAN 1000，获得有效地址和允许的网关。
- [ ] PPPoE为Connected/up，VLAN 1000，获得有效地址和允许的网关。
- [ ] IPoE与PPPoE同时存在且互不覆盖。
- [ ] 网络连通测试目标为`www.baidu.com`，丢包率0%，平均RTT小于100 ms。
- [ ] 新TestRun所有结果已保存、附Evidence并LOCKED。
- [ ] Regression结果为PASS，Defect完成关闭流转。
- [ ] 新Report与Archive生成成功且SHA256校验一致。
- [ ] Round 1–4历史记录未修改。

### HOLD条件

满足任一条件时继续保持Release `HOLD`：

- DUT仍为offline或无法稳定供电、启动、访问。
- ONU未达到O5，或Config/Match仍为`initial`/不匹配。
- 仍存在`LOSi/LOBi`或当前有效距离不可用。
- IPoE或PPPoE任一未连接、无有效地址或相互覆盖。
- 网络连通不满足0%丢包和平均RTT标准。
- 缺少必要Evidence、LOCKED结果、PASS Regression、Report或Archive完整性证明。

## 7. 最终结论模板

| 项目 | 填写内容 |
|---|---|
| 分析日期 | __________ |
| 执行人/复核人 | __________ / __________ |
| DUT型号/SN | __________ / 已脱敏：__________ |
| 根因分类 | 光链路 / ONU供电 / ONU软件 / SN认证 / ONT profile / OLT配置 / PON端口 / 其他：__________ |
| 根因证据 | __________ |
| 处理动作 | __________ |
| 新TestRun ID | __________ |
| ONU online | PASS / FAIL / BLOCKED；Evidence：__________ |
| O5 | PASS / FAIL / BLOCKED；Evidence：__________ |
| IPoE | PASS / FAIL / BLOCKED；Evidence：__________ |
| PPPoE | PASS / FAIL / BLOCKED；Evidence：__________ |
| 网络连通 | PASS / FAIL / BLOCKED；Evidence：__________ |
| Regression | ID：__________；结果：PASS / FAIL / BLOCKED |
| Report / Archive | __________ / __________ |
| 历史完整性核对 | PASS / FAIL；说明：__________ |
| BETA-ISSUE-001最终状态 | OPEN / VERIFIED / CLOSED |
| Release最终决策 | PASS / HOLD |

### 最终结论

经核对，`BETA-ISSUE-001`的根因为：__________。

采取的处理措施为：__________。处理后新TestRun `__________`中的ONU online、O5、IPoE、PPPoE和网络连通结果为：__________，对应Evidence为：__________。

Round 1–4及后续历史记录完整性核对结果为：__________。Regression结果为：__________，Report/Archive完整性校验结果为：__________。

因此，`BETA-ISSUE-001`最终状态判定为`__________`，V1 Release决策为`__________`。
