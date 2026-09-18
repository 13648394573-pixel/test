# ONU Test Workbench V2 Sprint 0 验收记录

## 验收范围

- 基线提交：`4633368`（V1 Test Management）
- 功能分支：`feature/v2-sprint-0-foundation`
- 验收日期：2026-09-18
- 范围：数据库、ORM、执行契约、状态机和迁移兼容性；不包含新页面、真实设备控制或 Runner Host。

## 验收结果

| 检查项 | 结果 |
|---|---|
| Alembic 拓扑 | 单一 head：`20260918_0020` |
| 空库升级 | 从空库升级至 head 成功；44 张表；`PRAGMA quick_check=ok`；0 条外键违规 |
| V1→V2 数据升级 | 从 `20260730_0007` 和 `20260811_0010` 升级成功 |
| 迁移专项测试 | 29 passed，215 deselected |
| 后端全量测试 | 244 passed，0 failed，3 warnings |
| 前端回归 | 22 个文件、48 tests passed |
| 前端生产构建 | TypeScript 与 Vite build 成功，53 modules transformed |
| Diff 检查 | `git diff --check 4633368..HEAD` 无错误 |

3 条后端 warning 分别来自 Pytest 未识别的 `asyncio_default_fixture_loop_scope` 配置项、Starlette TestClient 的 httpx 兼容弃用提示，以及 AnyIO BlockingPortal 别名弃用提示；本次没有隐藏或忽略测试失败。

## 迁移兼容性证明

完整 V1 闭环种子覆盖 Device、Test Case/Step、Project/Selection、Run/Result、Evidence、Defect/Regression、Report/Archive。升级后验证：

- 所有 V1 业务表记录数量不变；
- Result 结论及完整性状态不变；
- Evidence、Report、Archive 的 SHA256 不变；
- Evidence 与 Result 的共享关联保留；
- 历史 Run 使用 `execution_schema_version=1`、`source='MANUAL'`；
- 历史 Result 使用 `result_source='MANUAL'`；
- 历史 V2 Skill、Standard、Template 和恢复快照保持空值；
- 迁移不会根据旧文本猜测或创建 Skill/Standard；
- SQLite quick check 和 foreign key check 均通过。

## 安全边界

- Runner 数据库仅保存 Plugin/Action 标识、版本、哈希、Schema 和受控绑定，不保存任意脚本正文或命令文本。
- Credential 表只保存外部凭据引用；模型拒绝疑似 URL 内嵌凭据、换行符或秘密材料。
- Sprint 0 新增迁移中不存在 `password`、`token`、`script_body`、`command_text`、`web_selector` 等秘密或可执行载荷字段。
- 生产启动要求数据库已迁移到 Alembic head；ORM `create_all` 仅允许测试或明确的本地开发初始化。

## 已知限制与后续入口

- 尚无 Standard/Skill CRUD API 和管理页面；属于 Sprint 1。
- 尚无插件包导入、Runner Host、localhost 协议、模拟 Action 或 Windows 凭据实现；属于后续 Runner 工作。
- 尚未连接真实 ONU/OLT，也未实现 VLAN、QoS、IPv6 测试脚本；需要与测试人员按本地环境逐个封装 Skill。
- 尚未实现安装后双击启动与启动器自动迁移；属于安装部署阶段。
- 不在当前范围内：AI 自动测试、自动控制 OLT、自动登录 ONU、云平台、多用户权限和复杂自动化流程。

## 结论

Sprint 0 已建立 V2 Test Standard、Test Intelligence、Template、受控 Runner Registry 与 Execution Foundation 的可迁移后端基础，同时保留 V1 Test Management 数据和行为基线，可进入 Sprint 1 的 Skill 管理设计与实现评审。
