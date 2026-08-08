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
| `BETA-ISSUE-001` | 2026-07-30至2026-08-08 | Test Execution（外部DUT/实验室环境） | 授权目标DUT使用空闲ONT ID 48及Profile 10/10注册后，online、O5、IPoE、PPPoE及网络连通全部通过 | P1 | CLOSED | 现场接线恢复与目标DUT重新注册；无代码变更 | 否 |

## Round 1问题记录

### BETA-ISSUE-001：ONU光链路离线阻断真实业务验收

| 字段 | 记录 |
|---|---|
| Issue ID | `BETA-ISSUE-001` |
| 日期 | 2026-07-30 |
| 模块 | Test Execution（外部DUT/实验室环境） |
| 描述 | ONU在预期OLT端口存在历史档案，但当前为offline；无法完成O5、IPoE、PPPoE及外网连通性验证 |
| 严重级别 | P1（Beta验收阻塞；非已确认产品代码缺陷） |
| 当前状态 | CLOSED |
| 修复版本 | 2026-08-08现场接线恢复与目标DUT重新注册；无Test Workbench代码变更 |
| 是否影响Release | 否；专项恢复验证已取得全部正向PASS证据 |
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

#### Round 3执行记录

- 新TestRun：`fa7b1ecb-0603-45c4-8dcd-e3a7239dca5d`，`COMPLETED`。
- ONU Web：HTTP 200，本地管理面恢复。
- OLT状态：F/S/P `0/2/10`、ONT ID `36`，Run state `offline`，Config/Match state `initial`。
- 光链路：Last down cause `LOSi/LOBi`，当前距离为空，last distance `85 m`。
- IPoE、PPPoE、网络连通：因online/O5前置条件失败未执行，均记录为BLOCKED。
- Test Workbench结果：1 PASS、2 BLOCKED，全部LOCKED。
- Evidence：
  - `1ec5769e-bc86-4b87-913d-81d92f23bdac`
  - `9f5dfc47-3d39-436a-b6b6-9f4d33ccc337`
- Regression：追加第2条BLOCKED Regression，未自动改变Defect状态。
- Report/Archive：`RPT-000002`、`ARC-000002`，文件SHA256校验一致。
- 判定：本地管理面恢复不等于PON恢复，`BETA-ISSUE-001`继续OPEN。

#### Round 4预检记录

- 日期与基线：2026-08-03，`main` / `2500a28f0fb0c0e447b800a41b9ce035cc090951`。
- ONU Web：请求超时，Ping不可达。
- OLT SSH：连接成功，只读查询成功。
- OLT状态：F/S/P `0/2/10`、ONT ID `36`，Run state `offline`，Config/Match state `initial`。
- 光链路：Last down cause `LOSi/LOBi`，当前距离为空，last distance `85 m`。
- IPoE、PPPoE、网络连通：因online/O5前置条件失败未执行。
- Test Workbench：按“DUT恢复后创建新TestRun”规则，本次未创建Run；前三轮历史仍为3个Run、9个结果、2份Report、2份Archive和2条Regression。
- Evidence：
  - `C:\Users\admin\onu_test\screenshots\20260803_beta_round4\20260803_172931_04_ont_online.txt`
  - `C:\Users\admin\onu_test\screenshots\20260803_beta_round4\20260803_172931_04_ont_online.png`
- 判定：DUT尚未恢复，`BETA-ISSUE-001`保持OPEN，Release保持HOLD。

#### 专项恢复验证与关闭记录

- 日期与基线：2026-08-08，`main` / `01024495fb3d12f723b66a70c969db45b74a0ba4`。
- 授权：当前接入设备确认为目标DUT，允许使用空闲ONT ID及Profile 10/10注册并继续业务验证。
- DUT：XPON `UN-769XR`；完整SN与MAC仅保存于本地受控Workbench档案。
- OLT：F/S/P `0/2/10`、ONT ID `48`、Line/Service Profile `10/10`；目标ONT在线，`Match state=match`，但`Config state=failed`作为管理面观察项保留。
- PON：ONU Web显示`O5`，Tx `2.488809 dBm`，Rx `-6.619421 dBm`。
- IPoE：Connected，地址`192.168.87.7`，网关`192.168.87.1`。
- PPPoE：Connected，地址`10.11.20.214`，网关`10.11.20.1`。
- 网络连通：`www.baidu.com` 4发4收、0%丢包、平均RTT `12.006 ms`。
- 新TestRun：`b179fb82-f1bc-488a-ab2a-5bcdfc62b309`，3项结果均为PASS/LOCKED；历史3个Run及其Snapshot未修改。
- PASS Regression：`9f5cc967-f823-43a9-9ac9-44475b87c0a8`；`DEF-000001`已`CLOSED`。
- Report/Archive：`RPT-000003` / `ARC-000003`，SHA256校验通过。
- 根因归类：此前阻塞属于外部DUT接线/识别与PON接入条件；本次恢复后使用已确认目标DUT重新注册，未修改Test Workbench代码。
- 关闭判定：要求的ONU online、O5、IPoE、PPPoE和网络连通全部通过，`BETA-ISSUE-001`关闭，原链路阻塞导致的Release HOLD解除。正式打Tag前需人工确认是否接受`Config state=failed`与SN认证场景下的`LOID Error`观察项。

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
| P1 | 1 | 0 | 0 | 0 | 1 | 0 |
| P2 | 0 | 0 | 0 | 0 | 0 | 0 |

## V1 Release影响结论

| 检查项 | 当前结论 |
|---|---|
| 未关闭P0数量 | 0 |
| 未关闭P1数量 | 0 |
| 待评估问题数量 | 0 |
| 是否存在数据可信度风险 | 否；历史Run保留，新Run结果与Evidence均已LOCKED |
| 是否存在主流程阻断 | 否；真实PON/WAN正向验收已完成 |
| 当前是否影响V1 Release | 原链路阻塞不再影响；具备进入发布复核条件，打Tag前复核管理面观察项 |

结论说明：2026-08-08专项恢复验证中，目标DUT完成注册并取得ONU online、O5、IPoE、PPPoE及网络连通正向PASS证据；新Run全部结果LOCKED，PASS Regression关闭关联Defect，Report/Archive及SHA256校验完成。`BETA-ISSUE-001`已CLOSED，原链路阻塞HOLD解除。OLT仍显示`Config state=failed`且ONU Web显示`LOID Error`，但`Match state=match`且五项业务均实际通过；两项保留为打Tag前人工复核观察项，本阶段不创建Tag。

复核人：__________

复核日期：__________
