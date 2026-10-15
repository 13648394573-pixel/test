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
