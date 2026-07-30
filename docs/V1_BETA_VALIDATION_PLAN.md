# Test Workbench V1 Beta Validation Plan

## 验证基线

- 分支：`main`
- V1 Alpha Release Baseline：`8fb54baf0af434ec1f2d75384253a9b61bb62299`
- 验证对象：单机B/S架构下的手工测试记录闭环
- 适用设备：ONU、OLT、光猫
- 范围边界：不验证自动化执行、AI、多用户协作、云存储或企业级流程

## 1. Beta验证目标

1. 验证真实ONU/OLT场景可以完成“设备—用例—环境—执行—证据—缺陷—回归—报告—归档”闭环。
2. 验证Device、TestCase和Environment Profile变化不会影响历史Run、Report和Archive。
3. 验证LOCKED结果、Snapshot、Report和Archive不可修改，文件异常能被SHA256校验发现。
4. 验证FAIL/BLOCKED结果可以形成可追溯的Defect与追加式Regression记录。
5. 验证空库安装、历史数据库升级、长用例列表和较大附件下的基本稳定性。
6. 收集真实测试工程师的操作问题，区分发布阻断问题与可延期改进项。

## 2. 真实ONU/OLT测试流程

### 2.1 测试准备

- 备份SQLite数据库、Evidence、Report和Archive目录。
- 准备一台DUT、可用OLT/PON口、测试PC和业务网络。
- 确认OLT槽位/端口、VLAN、线路模板、业务模板和测试账号；保存证据前隐藏密码等敏感信息。
- 在设备库登记DUT类型、厂商、型号、SN、MAC及软硬件版本。
- 建立环境模板，记录OLT型号、F/S/P、PON口、VLAN、WAN模式、网络出口及其他必要参数。
- 选择覆盖基础信息、PON、WAN、业务连通性和异常场景的测试用例。

### 2.2 上线与业务验证

1. 访问ONU Web页面，核对型号、SN、MAC、软硬件版本并保存截图。
2. 在OLT侧人工执行ONT发现，核对F/S/P和SN后注册ONU。
3. 确认ONU处于O5/online状态，并记录OLT原始输出或脱敏截图。
4. 按实验室标准人工配置业务，至少覆盖一条实际使用的IPoE或PPPoE链路；如标准要求双WAN，则分别验证。
5. 检查ONU Web中的PON、WAN、TR069/Internet状态和地址信息。
6. 执行业务连通性测试，例如目标域名Ping；记录丢包率、时延及实际结果。
7. 对每条用例填写PASS、FAIL或BLOCKED，补充实际结果、阻塞原因和测试备注。
8. 上传截图、脱敏OLT输出、日志或配置文件作为Evidence，确认可以下载且hash一致。

### 2.3 缺陷、回归与交付

- 对锁定的FAIL/BLOCKED结果创建Defect，验证同一RunResult不能重复创建缺陷。
- 按合法状态流转处理Defect；对RESOLVED缺陷追加Regression。
- 验证Regression PASS使缺陷进入CLOSED，FAIL使缺陷进入REOPENED，BLOCKED仅记录结果。
- 锁定所有结果并完成Run，生成HTML Report，核对设备、用例、环境、结果、Evidence和Defect汇总。
- 创建一次Archive，校验ZIP中的HTML、manifest和Evidence；再次创建应返回409。
- 修改源Device、TestCase和Environment Profile后，确认历史Run、Report和Archive内容不漂移。

## 3. 验收步骤

### A. 安装与数据

- [ ] 在干净环境安装前后端依赖并启动服务。
- [ ] 从空SQLite数据库执行全部Alembic迁移。
- [ ] 使用一份旧基线数据库升级到最新迁移并核对历史数据。
- [ ] 验证SQLite外键已启用，删除关联数据不会产生孤立记录。

### B. 核心闭环

- [ ] 完成至少一台ONU或光猫的真实测试闭环。
- [ ] Device、TestCase、Environment Profile创建和编辑正常。
- [ ] 新Run正确生成设备和环境快照，RunResult正确生成用例快照。
- [ ] PASS、FAIL、BLOCKED及备注字段保存正确，LOCKED后拒绝修改。
- [ ] Defect状态流转、Evidence生命周期和Regression联动符合规则。

### C. 完整性与历史

- [ ] Profile或基础档案修改后，历史Snapshot保持不变。
- [ ] 手工替换或破坏Evidence文件后，下载或归档能报告hash异常。
- [ ] 已生成Report内容不随源数据修改而变化。
- [ ] Report HTML被修改后，下载或归档能发现完整性冲突。
- [ ] Archive不可更新，一个Report只能对应一个Archive。

### D. 报告、归档与稳定性

- [ ] 仅COMPLETED且所有结果LOCKED的Run可以生成Report。
- [ ] Report统计、缺陷汇总和Evidence清单与执行记录一致。
- [ ] ZIP可以正常解压，manifest路径、大小和SHA256与文件一致。
- [ ] 使用不少于100条用例和多个大附件完成一次测试，记录响应时间与磁盘占用。
- [ ] 关闭并重启前后端后，历史项目、附件、报告和归档仍可访问。

### E. 验收记录

- [ ] 每个失败步骤记录复现条件、期望结果、实际结果、截图或日志。
- [ ] 所有问题完成P0/P1/P2分级，并关联到具体模块和测试步骤。
- [ ] 验收结束后重新运行后端测试、前端测试和生产构建。

## 4. P0/P1/P2问题分类标准

| 等级 | 定义 | 典型情况 | 发布处理 |
|---|---|---|---|
| P0 | 阻断测试闭环、造成数据丢失/污染，或破坏不可变与完整性保证 | 无法启动或迁移；Run/Result/Report数据损坏；LOCKED仍可修改；归档遗漏或打包错误文件；敏感凭据泄露 | 立即停止验收；必须修复并完成全量回归，未关闭不得创建Tag |
| P1 | 核心能力严重错误，但数据可恢复或存在明确临时规避方式 | 设备/用例/环境无法正常维护；结果或缺陷状态错误；Evidence无法上传下载；报告统计错误；历史快照展示错误；常规规模下明显不可用 | V1 Alpha Tag前必须修复并验证；如确需接受，必须有书面风险批准 |
| P2 | 不影响闭环和数据可信度的一般问题 | 文案、布局、非关键提示、低频操作不便、轻微性能问题或文档缺漏 | 可带入Beta问题清单；需记录影响范围、规避方式和后续处理建议 |

分级原则：优先按数据安全、历史可信度和主流程影响判断；无法确定时先按较高等级登记，复现和评审后再降级。

## 5. V1 Alpha Tag创建条件

只有同时满足以下条件，才可在最终验收提交上创建V1 Alpha Tag：

- [ ] main包含全部已批准的V1 Alpha代码和发布文档，工作区干净。
- [ ] 空库迁移、旧库升级、后端测试、前端测试和生产构建全部通过。
- [ ] 至少一条真实ONU/OLT测试闭环完成，报告和归档可验证。
- [ ] Snapshot、LOCKED结果、Report、Archive和Evidence hash完整性验证通过。
- [ ] 未关闭P0为0，未关闭P1为0；P2均已记录并评估。
- [ ] 数据库和本地文件已完成可恢复备份，存储路径与权限检查通过。
- [ ] `README.md`、架构、数据库、API、CHANGELOG及发布清单与当前实现一致。
- [ ] 最终验收结果获得确认，并明确Tag指向的main commit。

建议使用带说明的Tag，例如`v1.0.0-alpha.1`。本计划只定义创建条件，不执行Tag创建。
