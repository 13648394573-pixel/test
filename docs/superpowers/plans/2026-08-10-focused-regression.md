# Focused Regression Run Implementation Plan

> Sprint 9 实施时使用 `superpowers:test-driven-development`，严格按任务顺序先写失败测试，再实现最小代码。

## 1. 目标与边界

从 Defect 或其失败证据创建只包含目标用例的精简回归 Run，复用现有 TestRun、RunResult、Evidence 与 Regression 闭环，同时保持历史 Run、Result 和 Snapshot 不可变。

本 Sprint 不增加自动化执行、不修改诊断范围、不改变已有结果锁定规则，也不进入 Sprint 10。

## 2. 数据模型设计

新增聚合关联表 `focused_regression_runs`，不改写既有业务表语义：

| 字段 | 类型/约束 | 说明 |
|---|---|---|
| `id` | UUID PK | 关联记录标识 |
| `test_run_id` | UUID FK, UNIQUE, RESTRICT | 对应精简 TestRun；一个 Run 只能属于一次精简回归 |
| `defect_id` | UUID FK, INDEX, RESTRICT | 来源 Defect |
| `source_run_result_id` | UUID FK, RESTRICT | 本次回归选择的失败或阻塞结果 |
| `defect_snapshot` | JSON NOT NULL | 创建时冻结的缺陷上下文 |
| `snapshot_version` | INTEGER NOT NULL, default 1 | 快照版本，V1 固定为 1 |
| `created_at` | DATETIME NOT NULL | 创建时间 |

`defect_snapshot` 固定包含：`defect_code`、`title`、`severity`、`status`、`resolution_notes`、`source_run_result_id`、`captured_at`。该表仅允许创建和查询，不提供更新或删除能力。

不修改 `regressions` 表。回归执行完成后，仍通过现有 Regression 创建入口把锁定后的 RunResult 追加到 Defect 历史。

## 3. Regression 关联方案

- 创建入口以 `defect_id` 为主上下文。
- Defect 必须处于 `RESOLVED`，否则返回 409。
- 默认来源为 `defects.source_run_result_id`；也可选择同一 Defect 已有 Regression 中结果为 `FAIL` 或 `BLOCKED` 的锁定 RunResult。
- 来源 Result 必须为 `LOCKED`，且必须能追溯到该 Defect；非法跨 Defect 来源返回 409。
- 每个 Defect 同时最多存在一个 `IN_PROGRESS` 的 Focused Regression Run；重复创建返回 409。
- Focused Run 结果锁定后，用户显式创建 Regression：`PASS` 使 Defect `RESOLVED → CLOSED`，`FAIL` 使其 `RESOLVED → REOPENED`，`BLOCKED` 只追加记录。沿用既有状态机，不自动 LOCK、不自动改缺陷状态。

## 4. API 设计

### 创建精简回归 Run

`POST /api/defects/{defect_id}/focused-regression-runs`

请求：

```json
{
  "device_source_id": "uuid",
  "environment_profile_id": "uuid",
  "source_run_result_id": "uuid|null"
}
```

响应 `201`：Focused Regression 元数据、创建后的 TestRun 摘要及唯一 RunResult。`source_run_result_id` 为空时使用 Defect 原始来源。

### 查询缺陷精简回归历史

`GET /api/defects/{defect_id}/focused-regression-runs`

响应 `200`：按 `created_at` 倒序返回精简回归历史及 Run 状态。

### 查询精简回归详情

`GET /api/focused-regression-runs/{run_id}`

响应 `200`：关联上下文、不可变缺陷快照、TestRun、唯一 RunResult 与现有 Evidence 摘要。

错误规则：资源不存在 `404`；状态、来源或活动 Run 冲突 `409`；请求格式或枚举非法 `422`。Router 只负责协议映射，Schema 校验输入输出，Service 执行业务规则和事务，Repository 负责持久化。

## 5. TestRun 创建流程

1. Router 校验请求并调用 Service。
2. Service 查询 Defect、来源 RunResult、Device、启用的 Environment Profile。
3. 校验 Defect 状态、来源归属、Result 锁定状态及活动 Run 唯一性。
4. 从来源 Result 的 `case_snapshot` 复制用例历史事实，不读取可能已变化的 TestCase。
5. 按现有规则从当前 Device 和 Environment Profile 生成新的设备、环境快照。
6. 同一事务创建：一个 `IN_PROGRESS` TestRun、一个 `DRAFT` RunResult、一个 `focused_regression_runs` 关联记录。
7. 后续结果编辑、Evidence、LOCK 使用现有 Test Execution/Evidence API。
8. LOCK 后由用户调用现有 Regression API完成状态闭环。

事务中任一步失败必须整体回滚，不留下孤立 Run 或关联记录。

## 6. Snapshot 策略

- Case Snapshot：复制来源 RunResult 已冻结的 `case_snapshot`，保证复测对象与失败证据一致。
- Device Snapshot：创建新 Run 时从用户选择的当前 Device 重新捕获，以记录本次实际 DUT 状态。
- Environment Snapshot：创建新 Run 时从启用 Profile 重新捕获，包含现有 `captured_at`。
- Defect Snapshot：记录创建瞬间的缺陷信息与解决说明，用于解释本次回归目的。
- 所有快照 `snapshot_version=1`，创建后不可更新；历史 Profile、Device、Case 或 Defect 变化不回写。
- 兼容历史数据：仅新建 Focused Regression Run 要求新增关联和缺陷快照，旧 Run 不做回填。

## 7. TDD 实施任务

### Task 1：Migration 与 ORM

先增加迁移测试，断言升级后表、外键、唯一约束和索引存在，降级只移除新表；再新增 `FocusedRegressionRun` ORM 和 Alembic revision `20260810_0009`。不修改既有字段。

验证：`python -m pytest backend/tests/test_migrations.py -q`

### Task 2：Repository

先测试原子创建、按 Run 查询、按 Defect 倒序查询和活动 Run 查询；再实现 Repository，确保 TestRun、RunResult 和关联记录共用一个事务边界。

验证：`python -m pytest backend/tests/test_focused_regression_repository.py -q`

### Task 3：Service 与快照

先覆盖 RESOLVED 门禁、来源归属、LOCKED 门禁、FAIL/BLOCKED 来源、活动 Run 冲突、单用例创建、快照复制和回滚；再实现 Service。禁止调用现有模块的私有实现，复用公开 Repository/Service 能力。

验证：`python -m pytest backend/tests/test_focused_regression_service.py -q`

### Task 4：API

先覆盖三条 API 的 201/200/404/409/422；再新增 Schema、Router 并注册到应用。API 不提供更新、删除或单独修改 Snapshot 的入口。

验证：`python -m pytest backend/tests/test_focused_regression_api.py -q`

### Task 5：前端基础流程

先写组件测试：从 Defect 创建、选择设备与环境、默认失败来源、冲突提示、历史列表、跳转 Run 详情；再实现 Defect 页面内的 Focused Regression 面板和 API client。结果编辑、Evidence 与 Regression 继续复用现有页面和接口。

验证：`npm.cmd test -- --reporter=dot --maxWorkers=1`

### Task 6：回归验证与文档

更新 Sprint 9 实施记录及 API/数据库文档，确认没有数据库文件、Evidence、构建产物或临时文件进入 Git。

验证：

```text
python -m pytest backend/tests -q
npm.cmd test -- --reporter=dot --maxWorkers=1
npm.cmd run build
git diff --check
git status
```

## 8. 测试策略

- Migration：空库 upgrade、现有最新库 upgrade、downgrade、SQLite foreign_keys 生效。
- Model/Repository：唯一约束、RESTRICT 外键、只读快照、事务回滚、排序。
- Service：状态矩阵、跨 Defect 拒绝、历史来源合法性、活动 Run 并发冲突、单 Result 保证。
- API：成功响应与 404/409/422 映射，响应不暴露文件绝对路径。
- 前端：创建表单、来源切换、错误反馈、历史列表、详情导航。
- 回归：Device、TestCase、TestExecution、Evidence、Defect/Regression、Environment、Report/Archive、Diagnostic 全量测试保持通过。

## 9. 验收标准

1. 可从 RESOLVED Defect 创建仅含一个目标 Case 的新 TestRun。
2. 可从原始失败结果或同 Defect 的失败/阻塞回归结果创建。
3. 跨 Defect、未锁定或 PASS 来源被拒绝并返回 409。
4. 同一 Defect 不可并行创建多个 IN_PROGRESS 精简回归 Run。
5. 新 Run 使用新的 Device/Environment Snapshot，Case Snapshot 与来源一致。
6. Defect Snapshot 创建后不可修改，版本为 1。
7. 历史 Run、RunResult、Snapshot 均不被修改。
8. Focused Run 只有一个 RunResult，仍支持实际结果、备注和 Evidence。
9. 系统不自动执行、不自动 LOCK、不自动变更 Defect。
10. 锁定后可通过既有 Regression API 完成 PASS/FAIL/BLOCKED 状态规则。
11. 前后端测试和生产构建全部通过。
12. Git 变更只包含 Sprint 9 范围，无运行数据和构建产物。

## 10. 风险控制

| 风险 | 控制措施 |
|---|---|
| 历史 Case 已删除或修改 | 只复制来源 Result 的不可变 Case Snapshot，不依赖当前 Case 记录 |
| 回归来源串到其他 Defect | Service 校验原始来源及 Regression 追溯链 |
| 重复或并行回归 | Service 活动 Run 门禁；事务内再次校验，冲突返回 409 |
| 新增关联破坏旧 Run | 新表只关联新 Run，迁移不回填、不修改旧记录 |
| 状态机出现两套逻辑 | Defect 状态变化只走现有 Regression Service |
| 原子创建中断产生脏数据 | TestRun、RunResult、FocusedRegressionRun 同事务提交 |
| Snapshot 漂移 | ORM/Service 禁止更新，API 不提供写入口，增加不可变测试 |
| 范围扩张为自动执行 | 本 Sprint 仅创建和管理精简手工 Run，不接入 Diagnostic 自动执行 |

## 11. 预计影响文件

- 后端：新增 focused regression model/repository/service/schema/router、迁移与对应测试；仅在应用注册点和 ORM 汇总处做必要接入。
- 前端：新增 Focused Regression API 类型、面板及测试；在 Defect 页面做入口接入。
- 文档：更新 Sprint 9 实施记录、API 和数据库说明。

实施期间不得改写 Device、TestCase、TestExecution、Evidence、Defect/Regression、Environment、Report/Archive、Diagnostic 的既有业务规则。
