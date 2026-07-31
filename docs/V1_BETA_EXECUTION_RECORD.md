# Test Workbench V1 Beta Execution Record

> 本文档用于记录一次真实ONU/OLT Beta验收。复制“真实ONU/OLT验收记录模板”章节即可创建新的验收批次。所有账号、密码、管理地址和用户数据必须在截图、日志及报告中脱敏。

## Beta执行总览

| 项目 | 记录 |
|---|---|
| 记录编号 | `BETA-20260730-001` |
| 验证状态 | Round 1已完成，真实业务正向验证被实验室链路阻断 |
| 验证开始日期 | 2026-07-30 |
| 验证结束日期 | 2026-07-30 |
| 执行人 | Codex（按测试工程师指令执行） |
| 复核人 | __________ |
| 验证分支 | `main` |
| 验证基线 | `df2efa30f97480b5c7b6441750e5eb9c3ff07725` |
| 关联计划 | `docs/V1_BETA_VALIDATION_PLAN.md` |

## Round 1实际验收记录

### 验收结论

本轮完成了Test Workbench数据闭环，系统侧未发现P0/P1产品缺陷。真实ONU在预期OLT端口处于`offline`，最近掉线原因为`LOSi/LOBi`，ONU Web不可达，因此PON O5及后续WAN正向业务验证均如实记录为`BLOCKED`，不判定为PASS。该实验室阻塞记录为`BETA-ISSUE-001`，在恢复物理链路并完成正向复测前，V1 Release验收结论为“暂缓”。

### DUT信息

| 项目 | 实际记录 |
|---|---|
| 设备类型/厂商 | ONU / Huawei |
| 型号、硬件、软件版本 | ONU Web不可达，未核实 |
| SN | 文档脱敏：`HWTC-****BBBB`；完整值仅保存在受控本地Workbench档案 |
| OLT定位 | F/S/P `0/2/10`，ONT ID `36` |
| OLT状态 | Control active；Run offline；Config/Match initial |
| 最近链路信息 | Last down cause `LOSi/LOBi`；last distance `85 m` |

### 测试环境

| 项目 | 实际记录 |
|---|---|
| Workbench基线 | `main` / `df2efa30f97480b5c7b6441750e5eb9c3ff07725` |
| 主机 | Windows 10.0.19045，Python 3.12.5，Node.js 24.16.0，npm 11.13.0 |
| Workbench服务 | `127.0.0.1:8000`、`127.0.0.1:5173`，健康检查通过 |
| Beta数据 | 独立SQLite数据库、Evidence和Report目录；均为git忽略的本地运行数据 |
| OLT | Huawei MA5800-X7；只执行只读查询，未下发配置 |
| 业务参数 | Line/Service Profile `10`，VLAN `1000`，预期IPoE + PPPoE |
| 测试PC网络 | `192.168.87.17/24`，网关`192.168.87.1`；ONU直连以太网接口断开 |

### Test Workbench闭环

1. 创建1条DUT档案、3条测试用例、1个环境模板和1个测试项目。
2. 创建首轮Run，自动生成Device/Case/Environment Snapshot，版本均为`1`。
3. 保存实际结果、阻塞原因和测试备注；上传真实OLT文本及截图Evidence。
4. 锁定全部结果：Workbench完整性用例`PASS`，PON与WAN用例`BLOCKED`；Run变为`COMPLETED`。
5. 验证LOCKED结果不可修改，修改请求返回`409`。
6. 基于LOCKED/BLOCKED结果创建`DEF-000001`，归类为外部DUT/光链路条件。
7. 创建第二个独立Run执行同用例复测；仍为`BLOCKED`，追加1条BLOCKED Regression，Defect状态不被自动改变。
8. 对首轮Run生成`RPT-000001`和`ARC-000001`；HTML与ZIP下载文件SHA256均与元数据一致，ZIP含报告、manifest及4份关联Evidence；重复创建Archive返回`409`。
9. 前端页面核对通过：设备、测试项目、两个Completed Run、报告统计与HTML/ZIP下载入口均可见。

### 测试结果

| Run | 用例 | 结果 | 完整性 | 说明 |
|---|---|---|---|---|
| 首轮 | `BETA-R1-TW-001` | PASS | LOCKED | Snapshot、Evidence、锁定、报告及归档闭环正常 |
| 首轮 | `BETA-R1-PON-001` | BLOCKED | LOCKED | ONT offline，LOSi/LOBi，无法验证O5 |
| 首轮 | `BETA-R1-WAN-001` | BLOCKED | LOCKED | PON/O5前置条件未满足，未推断WAN结果 |
| 回归 | `BETA-R1-TW-001` | PASS | LOCKED | 第二次历史记录独立生成 |
| 回归 | `BETA-R1-PON-001` | BLOCKED | LOCKED | 复测仍无可用光链路 |
| 回归 | `BETA-R1-WAN-001` | BLOCKED | LOCKED | WAN仍因PON前置条件阻断 |

### Evidence、Defect与Regression

| 类型 | 记录 |
|---|---|
| OLT在线状态文本 | Evidence `6af9d269-30d5-4161-a89f-1f7b869803ed`，显示offline及LOSi/LOBi |
| OLT状态截图 | Evidence `a87859ef-1cb0-4fff-b7a6-5949c9b7cab4` |
| OLT autofind文本 | Evidence `6a48b6ac-db1f-427f-90be-ea3aa72b8fb4`，无自动发现ONT |
| 回归Evidence | Evidence `d277a97c-e819-4ce0-8946-d2c3d8c181a3` |
| Defect | `DEF-000001`，S2，归类为外部实验室链路条件 |
| Regression | 1条，结果`BLOCKED`，追加成功且未自动修改Defect状态 |
| Beta Issue | `BETA-ISSUE-001`，P1验收阻塞项 |

### Report与Archive

| 项目 | 结果 |
|---|---|
| Report | `RPT-000001`，TOTAL 3 / PASS 1 / FAIL 0 / BLOCKED 2 / DEFECTS 1 |
| Archive | `ARC-000001`，342521 bytes |
| 完整性 | HTML SHA256匹配；ZIP SHA256匹配；Evidence打包成功 |
| 唯一性 | 同一Report第二次创建Archive返回`409` |

### Release影响评估

- Workbench闭环：通过，未发现产品P0/P1问题。
- 真实ONU/OLT业务验收：未通过正向条件，PON、WAN及外网连通性尚未形成PASS证据。
- 当前Release判断：**影响Release验收**。这是外部实验室/DUT条件阻塞，不是已确认的Workbench代码缺陷；恢复供电、光路和ONU管理连接后必须执行Round 2正向复测。
- Tag：本轮不创建Tag。

## Round 2预检记录

### 执行信息

| 项目 | 记录 |
|---|---|
| 日期 | 2026-07-31 |
| 验证分支 | `main` |
| 验证基线 | `f7c33b3f4b95c0f075ebfc96761dcddd496e1fbd` |
| Round 1历史记录 | 保留，未修改历史Run、Result、Snapshot、Evidence、Report或Archive |
| Round 2状态 | 预检BLOCKED，未进入正式TestRun |

### DUT恢复检查

| 检查项 | 期望 | 实际 | 结果 |
|---|---|---|---|
| ONU Web `192.168.1.1` | 页面可访问 | 请求超时，Ping不可达 | BLOCKED |
| OLT SSH | 可连接并执行只读查询 | Huawei MA5800-X7连接成功 | PASS |
| F/S/P与ONT ID | `0/2/10`、ONT ID `36` | 与预期一致 | PASS |
| ONU在线状态 | `online` | `offline` | BLOCKED |
| O5/匹配状态 | O5、Config/Match正常 | Config state `initial`、Match state `initial` | BLOCKED |
| 光链路信息 | 当前有效距离与在线信息 | 当前距离为空，last distance `85 m`，last down cause `LOSi/LOBi` | BLOCKED |
| IPoE | Connected/up | 未执行；O5前置条件不满足 | BLOCKED |
| PPPoE | Connected/up | 未执行；O5前置条件不满足 | BLOCKED |
| 网络连通 | 0%丢包且平均RTT小于100 ms | 未执行；WAN前置条件不满足 | BLOCKED |

### Evidence

- OLT原始文本：`C:\Users\admin\onu_test\screenshots\20260731_beta_round2\20260731_090347_04_ont_online.txt`
- OLT渲染截图：`C:\Users\admin\onu_test\screenshots\20260731_beta_round2\20260731_090347_04_ont_online.png`
- 查询为只读操作，未执行ONT注册、WAN配置或业务下发。
- 现有辅助工具的`PASS`只表示CLI命令成功返回；本轮依据原始字段判定，`Run state: offline`不满足业务PASS标准。

### Test Workbench处理

根据“恢复DUT后创建新的TestRun”的Round 2原则，本次预检确认DUT尚未恢复，因此：

1. 未创建新的TestRun。
2. 未修改Round 1历史Run或任何不可变Snapshot。
3. 未新增虚假PASS结果、Evidence、Regression、Report或Archive。
4. `BETA-ISSUE-001`继续保持OPEN，等待恢复物理光链路后重新开始Round 2。

### Round 2结论

- 要求的ONU online、O5、IPoE PASS、PPPoE PASS和网络连通PASS均未取得。
- 当前Release判断仍为**影响Release验收**。
- 本次不创建Tag，不开始Sprint，不扩展功能。

## 1. 验证日期

| 阶段 | 日期与时间 | 说明 |
|---|---|---|
| 环境准备 | __________ | __________ |
| DUT上线 | __________ | __________ |
| 用例执行 | __________ | __________ |
| 缺陷与回归 | __________ | __________ |
| 报告与归档 | __________ | __________ |
| 验收复核 | __________ | __________ |

## 2. 测试环境

### 2.1 Test Workbench环境

| 项目 | 实际值 |
|---|---|
| 操作系统 | __________ |
| Python版本 | __________ |
| Node.js/npm版本 | __________ |
| 浏览器及版本 | __________ |
| 后端地址 | __________ |
| 前端地址 | __________ |
| 数据库路径 | __________ |
| Evidence目录 | __________ |
| Report目录 | __________ |
| Archive目录 | __________ |
| 数据库/文件备份位置 | __________ |

### 2.2 OLT与网络环境

| 项目 | 实际值 |
|---|---|
| OLT厂商/型号 | __________ |
| OLT软件版本 | __________ |
| OLT管理地址 | 已脱敏：__________ |
| 机框/槽位/PON口（F/S/P） | __________ |
| ONT ID | __________ |
| Line Profile / Service Profile | __________ |
| 业务VLAN | __________ |
| WAN模式 | IPoE / PPPoE / 双WAN / 其他：__________ |
| 上联网络/网关 | 已脱敏：__________ |
| 测试PC地址 | 已脱敏：__________ |
| Ping目标 | __________ |

环境准备检查：

- [ ] SQLite、Evidence、Report和Archive已备份。
- [ ] OLT/PON口、业务模板和VLAN已确认。
- [ ] 测试账号可用，保存证据前已隐藏凭据。
- [ ] Test Workbench前后端启动及健康检查正常。

## 3. DUT信息

| 项目 | 标签值 | ONU Web值 | OLT识别值 | 是否一致 |
|---|---|---|---|---|
| 设备类型 | __________ | __________ | __________ | 是 / 否 / 不适用 |
| 厂商 | __________ | __________ | __________ | 是 / 否 / 不适用 |
| 型号 | __________ | __________ | __________ | 是 / 否 / 不适用 |
| SN | __________ | __________ | __________ | 是 / 否 / 不适用 |
| MAC | __________ | __________ | __________ | 是 / 否 / 不适用 |
| 硬件版本 | __________ | __________ | __________ | 是 / 否 / 不适用 |
| 软件版本 | __________ | __________ | __________ | 是 / 否 / 不适用 |
| Vendor ID | __________ | __________ | __________ | 是 / 否 / 不适用 |
| OLT模式 | __________ | __________ | __________ | 是 / 否 / 不适用 |

设备库记录ID：__________

信息差异说明：__________

## 4. 测试流程

结果填写：`PASS` / `FAIL` / `BLOCKED` / `N/A`。每个FAIL或BLOCKED必须填写问题编号或阻塞原因。

| 步骤ID | 测试动作 | 预期结果 | 实际结果 | 结果 | Evidence路径/编号 | 问题编号 |
|---|---|---|---|---|---|---|
| PRE-01 | 核对main基线与工作区 | HEAD与记录基线一致，工作区干净 | __________ | ______ | __________ | __________ |
| PRE-02 | 执行数据库迁移和健康检查 | 迁移成功，API健康检查正常 | __________ | ______ | __________ | __________ |
| ONU-01 | 访问ONU Web并保存登录页证据 | 页面可访问，无异常错误 | __________ | ______ | __________ | __________ |
| ONU-02 | 登录并核对生产信息 | 型号、版本、SN、MAC等与DUT档案一致 | __________ | ______ | __________ | __________ |
| OLT-01 | 人工执行ONT发现 | 在预期PON口发现目标SN | __________ | ______ | __________ | __________ |
| OLT-02 | 核对空闲ONT ID后注册ONU | 注册成功且未覆盖已有ONT | __________ | ______ | __________ | __________ |
| PON-01 | 查询ONU在线和匹配状态 | ONU处于O5/online，profile匹配 | __________ | ______ | __________ | __________ |
| WAN-01 | 人工配置并检查IPoE | WAN为Connected/up，地址有效 | __________ | ______ | __________ | __________ |
| WAN-02 | 人工配置并检查PPPoE（如适用） | WAN为Connected/up，与IPoE同时存在 | __________ | ______ | __________ | __________ |
| WAN-03 | 检查TR069/Internet状态 | 服务状态符合测试标准 | __________ | ______ | __________ | __________ |
| NET-01 | 执行Ping或业务连通性测试 | 丢包率和时延符合测试标准 | __________ | ______ | __________ | __________ |
| TW-01 | 创建设备、用例、环境和Run | Device/Case/Environment Snapshot正确生成 | __________ | ______ | __________ | __________ |
| TW-02 | 保存结果、备注和Evidence并锁定 | 字段保存正确，LOCKED后不可修改 | __________ | ______ | __________ | __________ |
| TW-03 | 创建Defect并执行Regression | 状态流转和PASS/FAIL/BLOCKED联动正确 | __________ | ______ | __________ | __________ |
| TW-04 | 完成Run并生成Report | 仅全部LOCKED的COMPLETED Run可生成报告 | __________ | ______ | __________ | __________ |
| TW-05 | 创建Archive并重复创建 | 首次成功，Evidence hash正确，第二次返回409 | __________ | ______ | __________ | __________ |
| TW-06 | 修改源档案后检查历史数据 | Run、Snapshot、Report和Archive不漂移 | __________ | ______ | __________ | __________ |
| POST-01 | 重启服务并重新访问历史数据 | 项目、Evidence、Report和Archive仍可访问 | __________ | ______ | __________ | __________ |

### 流程汇总

| 指标 | 数量 |
|---|---:|
| 总步骤 | __________ |
| PASS | __________ |
| FAIL | __________ |
| BLOCKED | __________ |
| N/A | __________ |

关键观察与操作体验：__________

## 5. 发现问题

每个问题单独填写一行；需要详细复现时，在表格下增加对应问题小节。

| 问题ID | 关联步骤 | 模块 | 标题 | 期望结果 | 实际结果 | 复现率 | Evidence | 临时规避 | 状态 |
|---|---|---|---|---|---|---|---|---|---|
| `BETA-ISSUE-001` | __________ | __________ | __________ | __________ | __________ | 必现/偶现/一次 | __________ | __________ | OPEN/RESOLVED/CLOSED |

### 问题详情模板

#### BETA-ISSUE-___：__________

- 发现时间：__________
- 前置条件：__________
- 复现步骤：
  1. __________
  2. __________
  3. __________
- 期望结果：__________
- 实际结果：__________
- 数据影响：无 / 可恢复 / 数据损坏 / 待确认
- 历史追溯影响：无 / 有 / 待确认
- Evidence或日志：__________
- 临时规避方式：__________
- 修复验证记录：__________

## 6. P0/P1/P2分类

| 等级 | 本次判定标准 | 问题编号 | 总数 | 未关闭数 |
|---|---|---|---:|---:|
| P0 | 阻断闭环、数据丢失/污染、不可变或hash保护失效、敏感信息泄露 | __________ | ___ | ___ |
| P1 | 核心能力严重错误，数据可恢复或存在明确规避方式 | __________ | ___ | ___ |
| P2 | 不影响闭环和数据可信度的一般体验、性能或文档问题 | __________ | ___ | ___ |

分级复核结论：__________

是否存在等级争议：否 / 是，说明：__________

## 7. 是否影响V1 Release

### Release结论

- [ ] **不影响**：无未关闭P0/P1，核心闭环与完整性验证通过。
- [ ] **有条件通过**：仅存在已记录P2，规避方式和后续建议明确。
- [ ] **影响发布**：存在P0/P1、数据可信度风险或核心流程未完成。

结论说明：__________

发布阻断问题：__________

必须完成的回归项：__________

是否满足V1 Alpha Tag条件：是 / 否

建议Tag目标Commit：__________

## 真实ONU/OLT验收记录模板

新验收批次应复制本文档并至少填写以下内容：

- [ ] 唯一记录编号、验证日期、执行人和复核人。
- [ ] Test Workbench commit、软件环境、数据库与文件存储路径。
- [ ] OLT型号、版本、F/S/P、ONT ID、Profile、VLAN和脱敏网络信息。
- [ ] DUT标签、ONU Web与OLT识别信息三方对比。
- [ ] ONU Web、ONT发现/注册、O5、WAN、TR069/Internet和Ping证据。
- [ ] Test Workbench结果、Evidence、Defect、Regression、Report和Archive记录。
- [ ] 所有FAIL/BLOCKED对应的问题编号、等级、复现步骤和Evidence。
- [ ] P0/P1/P2汇总、Release影响结论和复核签字。

### 验收签字

| 角色 | 姓名 | 日期 | 结论/签字 |
|---|---|---|---|
| Beta执行人 | __________ | __________ | __________ |
| 测试复核人 | __________ | __________ | __________ |
| Release确认人 | __________ | __________ | __________ |
