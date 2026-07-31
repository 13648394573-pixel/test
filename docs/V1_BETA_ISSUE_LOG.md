# Test Workbench V1 Beta Issue Log

## 台账信息

| 项目 | 内容 |
|---|---|
| Beta基线分支 | `main` |
| Beta基线Commit | `df2efa30f97480b5c7b6441750e5eb9c3ff07725` |
| 台账开始日期 | 2026-07-30 |
| 当前状态 | 执行中 |
| 关联执行记录 | `docs/V1_BETA_EXECUTION_RECORD.md` |

本台账只记录V1 Beta验证期间发现的问题。每个问题必须拥有唯一Issue ID，并关联复现步骤、严重级别、当前状态和Release影响。截图、日志和网络信息写入文档前必须脱敏。

## 问题汇总

| Issue ID | 日期 | 模块 | 描述 | 严重级别 | 当前状态 | 修复版本 | 是否影响Release |
|---|---|---|---|---|---|---|---|
| `BETA-ISSUE-001` | 2026-07-30，2026-07-31复测 | Test Execution（外部DUT/实验室环境） | Round 2预检仍显示ONU离线，LOSi/LOBi继续阻断O5、WAN和连通性正向验收 | P1 | OPEN | 环境恢复后复测 | 是 |

## Round 1问题记录

### BETA-ISSUE-001：ONU光链路离线阻断真实业务验收

| 字段 | 记录 |
|---|---|
| Issue ID | `BETA-ISSUE-001` |
| 日期 | 2026-07-30 |
| 模块 | Test Execution（外部DUT/实验室环境） |
| 描述 | ONU在预期OLT端口存在历史档案，但当前为offline；无法完成O5、IPoE、PPPoE及外网连通性验证 |
| 严重级别 | P1（Beta验收阻塞；非已确认产品代码缺陷） |
| 当前状态 | OPEN |
| 修复版本 | 环境恢复后复测 |
| 是否影响Release | 是；缺少真实业务正向PASS证据 |
| 关联验收步骤 | ONU-01、OLT-01、PON-01、WAN-01、WAN-02、WAN-03、NET-01 |
| 关联Defect ID | `DEF-000001` |
| Evidence | `6af9d269-30d5-4161-a89f-1f7b869803ed`、`a87859ef-1cb0-4fff-b7a6-5949c9b7cab4`、`6a48b6ac-db1f-427f-90be-ea3aa72b8fb4` |

#### 前置条件

1. Test Workbench运行在`main`基线`df2efa30f97480b5c7b6441750e5eb9c3ff07725`。
2. OLT MA5800-X7可访问，目标ONU应位于F/S/P `0/2/10`、ONT ID `36`。

#### 复现步骤

1. 在OLT按SN执行只读ONT状态查询。
2. 观察Run state为`offline`，Config/Match state为`initial`，Last down cause为`LOSi/LOBi`。
3. 查询ONT autofind，无自动发现ONT；访问ONU Web `192.168.1.1`超时。

#### 期望结果

ONU在预期端口online/O5，ONU Web可达，可以继续验证IPoE、PPPoE及外网连通性。

#### 实际结果

ONU离线且ONU Web不可达。Workbench如实保存并锁定BLOCKED结果，未把未执行的WAN测试标记为PASS或FAIL。

#### 影响分析

- 数据影响：无；结果、Snapshot、Evidence、Report和Archive完整性验证通过。
- 历史追溯影响：无。
- 影响设备或环境：目标ONU、PON物理链路或供电/接线条件。
- 复现率：本轮两次Run均复现。
- 临时规避方式：无；必须恢复DUT供电、光纤连接及ONU管理链路。

#### 修复与验证

- 根因：当前证据指向外部DUT/光链路条件，需现场检查后确认。
- 修复Commit或版本：不适用，未修改Test Workbench代码。
- 回归范围：ONU Web、OLT online/O5、IPoE、PPPoE、TR069/Internet、Ping及完整Report/Archive。
- 回归结果：2026-07-31 Round 2预检仍为BLOCKED；因DUT未恢复，未创建正式TestRun。
- 验证人及日期：Codex / 2026-07-30、2026-07-31。
- 关闭说明：Round 2取得真实正向PASS证据后方可关闭。

#### Round 2预检补充证据

- OLT SSH：连接成功，只读查询成功。
- F/S/P：`0/2/10`；ONT ID：`36`。
- 实际状态：Run state `offline`，Config/Match state `initial`。
- 光链路：Last down cause `LOSi/LOBi`，当前距离为空，last distance `85 m`。
- ONU Web：`192.168.1.1`访问超时。
- Evidence：
  - `C:\Users\admin\onu_test\screenshots\20260731_beta_round2\20260731_090347_04_ont_online.txt`
  - `C:\Users\admin\onu_test\screenshots\20260731_beta_round2\20260731_090347_04_ont_online.png`
- 判定：问题继续复现，状态保持OPEN；不得以CLI命令执行成功替代ONU online/O5业务PASS。

## 字段填写规则

### Issue ID

- 格式：`BETA-ISSUE-NNN`，例如`BETA-ISSUE-001`。
- 编号创建后不得复用或修改。

### 模块

从以下范围选择最接近的一项：

- Foundation / Migration
- Device Library
- Test Case Library
- Test Execution
- Defect & Regression
- Evidence & Result Integrity
- Environment Snapshot
- Report & Archive
- Frontend / Usability
- Documentation

### 严重级别

| 等级 | 判定标准 | Release处理 |
|---|---|---|
| P0 | 阻断测试闭环、导致数据丢失/污染、破坏不可变或hash保护，或泄露敏感信息 | 必须立即停止相关验收；修复并完成全量回归前不得Release |
| P1 | 核心能力严重错误，但数据可恢复或存在明确临时规避方式 | V1 Release前必须修复并验证；例外接受需要明确风险批准 |
| P2 | 不影响测试闭环和数据可信度的一般体验、性能或文档问题 | 可以带入已知问题清单，但必须记录影响与规避方式 |

无法确定等级时，先按较高等级记录，完成复现和影响评审后再调整。

### 当前状态

| 状态 | 含义 |
|---|---|
| OPEN | 已确认问题，尚未处理 |
| IN_PROGRESS | 正在定位或修复 |
| RESOLVED | 已完成处理，等待验证 |
| VERIFIED | 已完成回归验证 |
| CLOSED | 已确认关闭 |
| WONT_FIX | 明确不修复，必须记录原因和风险接受结论 |

### 修复版本

- 未计划：填写`未计划`。
- 已修复：填写修复Commit、版本号或Tag。
- 仅文档/环境处理：填写对应文档Commit或环境调整记录。

### 是否影响Release

- `是`：存在未关闭P0/P1，或问题影响数据可信度、主流程和发布门禁。
- `否`：问题不影响闭环，或已完成修复和回归验证。
- `待评估`：影响尚未确认，必须补充验证结论后再关闭问题。

## 单问题记录模板

复制本节，为每个问题创建独立记录。

### BETA-ISSUE-___：__________

| 字段 | 记录 |
|---|---|
| Issue ID | `BETA-ISSUE-___` |
| 日期 | __________ |
| 模块 | __________ |
| 描述 | __________ |
| 严重级别 | P0 / P1 / P2 |
| 当前状态 | OPEN / IN_PROGRESS / RESOLVED / VERIFIED / CLOSED / WONT_FIX |
| 修复版本 | __________ |
| 是否影响Release | 是 / 否 / 待评估 |
| 关联验收步骤 | __________ |
| 关联Defect ID | __________ / 不适用 |
| Evidence路径或编号 | __________ |

#### 前置条件

1. __________
2. __________

#### 复现步骤

1. __________
2. __________
3. __________

#### 期望结果

__________

#### 实际结果

__________

#### 影响分析

- 数据影响：无 / 可恢复 / 数据损坏 / 待确认
- 历史追溯影响：无 / 有 / 待确认
- 影响设备或环境：__________
- 复现率：必现 / 偶现 / 一次 / 待确认
- 临时规避方式：__________

#### 修复与验证

- 根因：__________
- 修复Commit或版本：__________
- 回归范围：__________
- 回归结果：PASS / FAIL / BLOCKED / 未执行
- 验证人及日期：__________
- 关闭说明：__________

## 分类统计

| 等级 | 总数 | OPEN | IN_PROGRESS | RESOLVED | VERIFIED/CLOSED | WONT_FIX |
|---|---:|---:|---:|---:|---:|---:|
| P0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P1 | 1 | 1 | 0 | 0 | 0 | 0 |
| P2 | 0 | 0 | 0 | 0 | 0 | 0 |

## V1 Release影响结论

| 检查项 | 当前结论 |
|---|---|
| 未关闭P0数量 | 0 |
| 未关闭P1数量 | 1 |
| 待评估问题数量 | 0 |
| 是否存在数据可信度风险 | 否 / 是 / 待评估 |
| 是否存在主流程阻断 | 是：真实PON/WAN正向验收被外部链路条件阻断 |
| 当前是否影响V1 Release | 是：需完成Round 2正向复测 |

结论说明：Workbench数据闭环本身通过；2026-07-31 Round 2预检确认真实DUT/实验室链路仍不可用，尚未取得ONU online、O5、IPoE、PPPoE及网络连通正向PASS证据。

复核人：__________

复核日期：__________
