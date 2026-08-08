# Test Workbench V1 Maintenance Log

## 1. 当前版本信息

| 项目 | 当前值 |
|---|---|
| 产品版本 | `V1.0.0` Stable |
| Release日期 | 2026-08-08 |
| Git Tag | `v1.0.0` |
| Release Commit | `22a7c2b95f969068300013963c9971306a75d79c` |
| 维护阶段 | 真实工作场景观察；V1.0.0只修Bug，不扩展核心范围 |

### 当前核心能力

- Device Library：ONU、OLT、光猫等DUT设备档案管理。
- Test Case Library：测试用例、步骤、优先级和启停管理。
- Test Execution：测试项目、设备/用例选择和手工执行记录。
- Result Integrity：PASS、FAIL、BLOCKED结果，实际结果、阻塞原因、备注及LOCKED保护。
- Evidence：RunResult或Defect附件管理与SHA256完整性校验。
- Environment Snapshot：环境模板、参数及Run不可变环境快照。
- Defect & Regression：缺陷生命周期、追加式回归和状态联动。
- Report & Archive：不可变HTML报告、结果/缺陷汇总及ZIP归档。

## 2. 日常使用记录模板

每次完成一个真实测试任务后复制本节填写。记录应引用Workbench中的Project、Run、Defect、Report或Archive编号；不得写入明文账号、密码、完整SN/MAC或未脱敏网络信息。

### 使用记录 OBS-___：__________

| 字段 | 记录 |
|---|---|
| 日期 | __________ |
| 测试设备 | 类型/厂商/型号：__________；设备标识已脱敏：__________ |
| 项目 | Project：__________；版本：__________ |
| 使用流程 | 设备档案 → 用例/模板 → 环境 → TestRun → 结果/Evidence → Defect/Regression → Report/Archive；实际流程：__________ |
| 测试准备时间 | __________（设备、用例、环境及接线准备） |
| 执行时间 | __________（从创建TestRun到全部结果LOCKED） |
| 截图整理时间 | __________（Evidence采集、整理、上传及核对） |
| 报告生成时间 | __________（Report、Archive生成及校验） |
| 总耗时 | __________ |
| 遇到问题 | 无 / 有；Issue ID及描述：__________ |
| 是否影响测试效率 | 否 / 是；影响环节和额外耗时：__________ |
| 可优化点 | __________ |

### 本次结论

- 测试任务是否完成：是 / 否 / BLOCKED
- 数据闭环是否完整：是 / 否；缺失项：__________
- 是否产生V1.1候选需求：否 / 是；候选编号：__________

### 使用记录 OBS-001：真实ONU/OLT业务闭环

| 字段 | 记录 |
|---|---|
| 日期 | 2026-08-08 |
| 测试设备 | ONU；XPON UN-G113；SN/MAC已脱敏 |
| 测试项目 | `Maintenance OBS-001 Real ONU Validation`；版本 `v1.0.0` |
| Workbench记录 | Project `2062d6e5-548e-42ee-8fb4-0933f7e0e01f`；Run `23c6da3d-b113-40c5-9613-e9bed361dd0a` |
| 使用流程 | DUT预检 → OLT autofind → 使用空闲ONT ID 50及Profile 10/10注册 → O5确认 → IPoE/PPPoE确认 → 双WAN Ping → Evidence上传 → 5项结果PASS并LOCKED → Report → Archive |
| 传统测试方式耗时 | 本轮未做同期传统流程对照，不形成节省时间结论；后续Observation补充同类任务基线 |
| Workbench耗时 | 约6分钟，包含空库下的设备、5条用例、环境、Project、Run、Evidence、Report及Archive录入与核验 |
| 测试准备时间 | 约4分钟：链路可达性、ONT发现、端口占用及空闲ONT ID确认 |
| 执行时间 | 约6分钟：注册、O5、IPoE、PPPoE及两个WAN出口Ping |
| 截图整理时间 | 约2分钟：自动截图、OLT输出及双WAN Ping证据核对 |
| 报告生成时间 | 少于1分钟：生成 `RPT-000001` 和 `ARC-000001` 并完成SHA256校验 |
| 测试结果 | PASS；ONU online、O5、IPoE up、PPPoE up；IPoE与PPPoE分别Ping `www.baidu.com`，均3发3收 |
| Evidence | 6个附件；文件存在且SHA256全部匹配 |
| 遇到的问题 | ① OLT `Match state=mismatch`、ONU `LOID Error`，但业务全部通过，作为外部DUT/Profile观察；② 当前半自动Ping控件定位与该固件“Go”按钮不兼容，改为手工选择两个WAN出口；③ 本次非UI脚本经Windows管道写入中文时出现字符损失，英文Case Code、状态、Evidence和Hash不受影响，历史Run保持不修改 |
| 问题等级 | ① P3；② P2；③ P2（非标准录入路径观察） |
| 是否影响测试效率 | 是，Ping手工回退与非UI录入增加约3分钟；不影响设备业务判定和证据完整性 |
| 是否进入V1.1候选需求 | 是；`V11-CAND-001`：自动化执行/证据采集需适配不同ONU诊断控件，累计5次后评审 |

#### OBS-001结论

- TestRun状态：`COMPLETED`。
- 结果完整性：5/5 `PASS + LOCKED`。
- Report：`5ad5fd23-a17b-4d48-8a67-e82d0b9d5fbc`，HTML hash验证通过。
- Archive：`c5ac1adc-b996-4ed6-9e14-38907d070279`，ZIP hash验证通过。
- Defect/Regression：无产品缺陷，不创建Defect或Regression。
- Maintenance Observation进度：1/5。

### 使用记录 OBS-002：已注册ONU持续业务复测

| 字段 | 记录 |
|---|---|
| 日期 | 2026-08-08 |
| 测试设备 | ONU；XPON UN-G113；沿用已注册ONT ID 50，SN/MAC已脱敏 |
| 测试项目 | 已注册ONU在线、O5、双WAN状态与连通稳定性复测 |
| 使用流程 | OLT只读在线查询 → ONU Web状态采集 → PON/O5确认 → IPoE/PPPoE状态确认 → 双WAN Ping → IPoE异常分层复测 → 证据核验 |
| 传统测试方式耗时 | 本轮未做同期传统流程对照，不形成节省时间结论 |
| Workbench耗时 | 本轮按数据库冻结规则未创建TestRun、Report或Archive；维护记录约3分钟 |
| 测试准备时间 | 约1分钟：确认沿用现有F/S/P `0/2/10`、ONT ID 50及Profile 10/10，不重复注册或下发配置 |
| 执行时间 | 约3分钟：OLT在线查询、Web状态采集及双WAN Ping；IPoE异常追加诊断约1分钟 |
| 截图整理时间 | 约1分钟：OLT、WAN、PON及5组Ping证据自动保存并核对 |
| 报告生成时间 | 少于1分钟：外部测试工具生成JSON/HTML/DOCX；按冻结规则未写入Workbench Report/Archive |
| 测试结果 | 最终PASS；ONU持续online约24分钟、O5、IPoE up、PPPoE up；PPPoE首次Ping 3/3；IPoE首次域名Ping 0/3，随后网关、公共IP和域名复测均3/3 |
| Evidence | 新增独立OLT、WAN、PON、PPPoE Ping、IPoE首次失败及三项IPoE复测证据 |
| 遇到的问题 | ① 自动Ping仍无法识别该固件“Go”按钮，连续第2次需要手工回退；② IPoE首次域名Ping 0/3，但WAN保持up，网关/公共IP/域名立即复测均通过；③ OLT `Match state=mismatch`、ONU `LOID Error`持续存在但不影响业务 |
| 问题等级 | ① P2；② P2（瞬时连通异常，未稳定复现）；③ P3 |
| 是否影响测试效率 | 是，手工回退和分层复测额外增加约2分钟；不影响最终业务判定 |
| 是否进入V1.1候选需求 | 是；`V11-CAND-001`出现次数更新为2；新增`V11-CAND-002`：Ping失败后自动重试并执行网关/公共IP/域名分层诊断 |

#### OBS-002结论

- 最终结果：PASS。
- ONU/OLT：`online + O5`。
- WAN：`IPoE up + PPPoE up`。
- 连通性：PPPoE 3/3；IPoE首次0/3，后续三项复测均3/3。
- 数据库：未修改；未创建TestRun、Defect、Regression、Report或Archive。
- Maintenance Observation进度：2/5。

### 使用记录 OBS-003：真实版本回归与资产复用

| 字段 | 记录 |
|---|---|
| 日期 | 2026-08-08 |
| 测试设备 | 复用现有ONU Device `ef6033f6-ccca-48e1-bccb-329da2d4f070`；XPON UN-G113；SN/MAC已脱敏 |
| 测试项目 | 复用 `Maintenance OBS-001 Real ONU Validation`，执行独立版本回归Run |
| Workbench记录 | 新Run `2dfbb1f0-dfd6-4511-b246-a53b2b522e22`；历史Run由1增至2，旧Run前后内容一致 |
| 使用流程 | 复用Device/TestCase/Environment/Project → 创建新TestRun → OLT/Web版本回归 → 双WAN Ping及IPoE分层复测 → Evidence上传 → 5项PASS并LOCKED → Report → Archive |
| 传统测试方式耗时 | 本轮未做同期传统流程对照，不形成节省时间结论 |
| Workbench耗时 | 少于1分钟：复用现有资产创建Run、保存5项结果、上传9个Evidence并生成Report/Archive；设备侧回归另约4分钟 |
| 测试准备时间 | 约1分钟：读取1个Device、5条TestCase、1个Environment Profile和1个Project，无需重新建档 |
| 设备复用体验 | 良好；直接使用现有Device创建新Run，自动生成设备快照，未修改源Device和历史Run |
| 用例复用体验 | 5/5用例直接复用并自动生成结果；既有用例中的中文字符损失被忠实带入新快照，Case Code仍可识别，但报告可读性受影响 |
| 环境复用体验 | 良好；直接复用 `OBS-001 ONU/OLT Lab`，环境快照自动生成，无需重填F/S/P、Profile和VLAN |
| Evidence整理时间 | 约1分钟；9个附件均上传并通过SHA256；同一WAN截图需分别上传到IPoE和PPPoE结果，存在重复整理 |
| Report/Archive体验 | `RPT-000002`、`ARC-000002`均在1分钟内生成，HTML/ZIP hash验证通过；归档包含9个本轮Evidence |
| 测试结果 | 最终PASS；ONU online、O5、IPoE/PPPoE均up；PPPoE首次3/3；IPoE首次0/3，网关、公共IP和域名复测均3/3 |
| 新发现问题 | ① 自动Ping控件兼容问题连续第3次出现；② IPoE首次0/3、随后全通过的模式连续第2次出现；③ Evidence缺少批量上传或一份证据关联多个结果的整理方式；④ 源用例已有字符损失会进入不可变快照与报告 |
| 问题等级 | ① P2；② P2；③ P2；④ P2（源数据质量观察） |
| 是否影响测试效率 | 是，Ping回退、分层复测和重复Evidence关联增加约3分钟；不影响最终业务判定和文件完整性 |
| 是否进入V1.1候选需求 | `V11-CAND-001`更新为3次；`V11-CAND-002`更新为2次；新增`V11-CAND-003`：Evidence批量上传及多结果关联 |

#### OBS-003结论

- 新TestRun：`COMPLETED`，5/5 `PASS + LOCKED`。
- Evidence：9个，文件及SHA256全部有效。
- Report：`95f63bf6-ec26-4bf9-a47f-35d4a0196001`，HTML hash有效。
- Archive：`db4b080d-e71d-49ed-888c-539596f4fc8d`，ZIP hash有效。
- 历史完整性：旧Run未修改。
- Maintenance Observation进度：3/5。

## 3. 问题分类

| 等级 | 定义 | 维护处理原则 |
|---|---|---|
| P0 | 阻塞使用；无法完成核心测试闭环，或存在数据丢失、污染、完整性破坏及敏感信息泄露风险 | 立即停止受影响使用；优先修复并完成全量回归后发布补丁版本 |
| P1 | 明显降低效率；核心流程可继续，但存在稳定复现的严重错误或高成本规避步骤 | 评估进入最近补丁版本；记录规避方式、影响范围和回归要求 |
| P2 | 体验优化；不影响数据可信度和核心闭环，但操作、展示或性能可以改善 | 记录真实频次和节省时间预估，作为V1.1排序依据 |
| P3 | 未来想法；当前无明确阻塞、频次或收益数据 | 仅进入候选池观察，不承诺版本和开发时间 |

所有问题至少记录：Issue ID、日期、场景、复现步骤、等级、Evidence、规避方式、Release影响和当前状态。

## 4. V1.1候选需求池

候选需求必须来源于真实使用记录。进入候选池不代表批准开发；只有具备重复场景、实际耗时或质量影响的数据，才进入V1.1评审。

### Maintenance Observation门禁

- 最低样本：5次维护期真实ONU/OLT测试记录。
- 当前进度：3/5。
- 当前状态：OBSERVING，尚未满足V1.1方向评审条件。
- Beta/RC阶段的历史验证记录不替代维护期真实使用记录。
- 每次真实测试完成后新增一条记录，保留既有记录，不覆盖历史数据。

### 分类

- 测试模板
- 自动化执行
- 证据采集
- 数据统计
- 设备管理
- 报告优化
- 其他

### 候选需求记录

| 候选ID | 日期 | 分类 | 真实场景与问题 | 出现次数 | 当前额外耗时 | 预期收益 | 关联记录/Issue | 优先级 | 状态 |
|---|---|---|---|---:|---|---|---|---|---|
| `V11-CAND-___` | __________ | __________ | __________ | ___ | __________ | __________ | __________ | P1/P2/P3 | OBSERVING / REVIEW / ACCEPTED / REJECTED |
| `V11-CAND-001` | 2026-08-08 | 自动化执行 / 证据采集 | 不同ONU固件的Ping提交控件不同，当前规则定位失败，需要手工选择IPoE/PPPoE出口并执行 | 3 | 累计约6分钟 | 降低人工回退并稳定采集双WAN连通证据 | `OBS-001`、`OBS-002`、`OBS-003` | P2 | OBSERVING |
| `V11-CAND-002` | 2026-08-08 | 自动化执行 / 证据采集 | IPoE首次域名Ping 0/3，但网关、公共IP和域名立即复测均3/3，需要自动区分瞬时异常与稳定故障 | 2 | 累计约2分钟 | 降低误判并自动形成分层诊断证据 | `OBS-002`、`OBS-003` | P2 | OBSERVING |
| `V11-CAND-003` | 2026-08-08 | 证据采集 | 同一WAN截图需要分别上传到IPoE与PPPoE结果，多个Evidence缺少批量整理和多结果关联方式 | 1 | 约1分钟 | 减少重复上传、关联和归档文件体积 | `OBS-003` | P2 | OBSERVING |

### 评审规则

1. 不根据单次主观感受直接立项。
2. 未累计至少5次维护期真实测试记录前，不评审V1.1方向。
3. 优先处理高频、可量化节省时间或降低数据风险的需求。
4. 自动化执行仅作为V1.1候选分类，不改变V1.0.0“手工测试记录闭环”的定位。
5. 与当前核心范围无关的想法保持P3观察，不创建Sprint或模块。

## 5. 版本策略

### V1.0.0

- 只修Bug，不增加大功能。
- 修复必须关联真实Issue、复现步骤和回归证据。
- 不改变现有数据库设计、Snapshot/LOCKED不可变规则和单机B/S架构，除非另行完成版本评审。
- 补丁发布采用`v1.0.x`，发布前执行后端、前端、生产构建和受影响真实场景回归。

### V1.1

- 根据本日志中的真实使用数据规划。
- 在需求评审前不创建Sprint、不承诺功能和日期。
- 评审输入至少包括：使用频次、额外耗时、问题等级、现有规避方式、预期收益和回归范围。
- 经范围确认后再独立完成设计、Sprint计划和开发分支准备。
