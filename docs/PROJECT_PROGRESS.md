# Test Workbench 项目进度

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
