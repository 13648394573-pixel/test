# ONU Skill Task 8 实施记录

日期：2026-10-10。修复前主线基线：`0e915f2`。
开发分支：`codex/skill-execution`。本轮仅实现 Task 8，不进入 Task 9–12。

## 领域能力

- 在同一 SQLite 事务中创建 LOCAL_RUNNER Run、Result、DEVELOPMENT Session 和初始事件。
- 保存设备、用例、环境、Skill、参数、标准及执行步骤快照；拒绝明文秘密字段、调用方预置审批、未知参数及同设备并发活动会话。
- 每次 advance 最多执行一个受控动作或产生一条人工确认；步骤进度由追加式事件推导，不依赖进程内游标。
- 执行动作前持久化 ACTION_STARTED；未持久化结果的动作禁止自动重放，转入 RECOVERY_REQUIRED。
- 变更审批绑定适配器返回的精确 preview_hash，拒绝重复、跨会话或不匹配的响应。
- 支持顺序隔离与严格双 WAN 分支；配置结束时显式选择 RESTORE 或 KEEP。
- 证据通过已有存储边界写入，关联 Result、Session、Step 与 E1–E6；判定前重新核对 SHA256、脱敏标记及必要来源。
- 使用执行时标准快照判断功能 PASS/FAIL/BLOCKED；必要证据不完整时总体 BLOCKED；完成后通过现有锁定服务封存结果。

## 安全边界与实施裁决

1. 当前 MA5800 remove_test_services 仅删除指定 service-port，不证明 IPoE Host 已禁用。因此顺序隔离需要额外人工确认；不得将它当成已实现完整自动清理。
2. 当前 restore_snapshot 仅处理注册，不保证 WAN/service-port 全部恢复。编排比较完整前后快照；不一致或无法核验时生成 MANUAL_REQUIRED，保持 Result 为 DRAFT，不伪造恢复完成。
3. 当前基线标准没有明确的客户简化许可。因此 CUSTOMER_SIMPLIFIED 暂时拒绝；严格模式可执行。后续客户标准接入须单独审核，不能由运行参数绕过。
4. Runner 在本领域通过内部执行接口注入。正式的凭据、目标解析、适配器装配、API 和启动恢复入口属于 Task 9；本轮没有新增接口，也没有连接真实设备执行变更。
5. 缺失标准绑定事实时 BLOCKED。底层 Action 返回 PASS 不等于产品 PASS；现有适配器的原始字段仍需在正式装配时提供可核验的标准事实，不得补填未经验证的 online/O5 或 PC 承载结论。

## 验证范围

基础核对 26 passed；新增领域测试最终 36 passed。覆盖事务回滚、参数校验、快照分离、事件幂等冲突、人工审批、两个执行分支、中断恢复、锁定、证据缺失/重复来源/脱敏/Hash 校验及恢复快照差异。

独立审核提出两项阻塞问题，均先补充测试复现失败，再完成修正：

- 已完成的设备 FAIL 不被缺失的下游事实覆盖；明确环境阻塞仍优先 BLOCKED，证据不完整仍禁止总体 PASS。
- 动作执行声明按步骤及尝试次数匹配；第一次等待审批的结果不能遮蔽第二次已开始但没有结果的动作。此时只能进入恢复处理，不重复下发。

修正后完整后端回归：395 passed（229.90 秒）。执行时将 PYTHONPATH 指向本 worktree 的 backend，并使用独立短路径临时目录，避免 Windows 默认临时目录权限及长路径问题。git diff --cached --check 无错误。未修改前端，未重新运行前端测试或构建。

真实实验室门槛仍未完成：完整 PASS、受控 FAIL、BLOCKED/恢复记录必须在 Task 12 形成。Skill 与标准继续保持 DRAFT/DEVELOPMENT，不自动发布，不等同于平台完整 Skill 已交付。
