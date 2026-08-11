# History & Evidence Efficiency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为历史 TestRun 增加稳定可读编号、组合筛选与 2–5 个 Run 结果比较，并支持一次上传多份 Evidence、将同一 Evidence 关联到同一 Run 的多个结果。

**Architecture:** 在既有 Router → Schema → Service → Repository → Model 分层上增量扩展。`TestRun.run_no` 提供不可变的全局可读编号；新的 `run_history` 只读上下文负责筛选和比较；`EvidenceRunResultLink` 保存 Evidence 与 RunResult 的多对多关联，同时保留 `Evidence.run_result_id` 作为兼容旧数据与现有存储路径的主归属。Report Snapshot 在生成时展开关联，Archive 按 Evidence ID 去重后只打包一份文件。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2、Alembic、SQLite、Pydantic、React 19、TypeScript、Vitest、Testing Library、Vite。

## Global Constraints

- 仅在 `feature/history-evidence-efficiency` 及其独立 worktree 中实施。
- 严格使用 TDD：先写失败测试，再实现最小代码，再执行聚焦验证。
- 不修改历史 Run、RunResult、Device/Case/Environment Snapshot 或已生成 Report/Archive Snapshot。
- LOCKED RunResult 的结果字段保持不可修改，也不得新增或删除 Evidence 关联。
- Evidence 仍只保存元数据和文件路径；不复制相同物理文件。
- Evidence 多关联仅允许同一个 TestRun 内的 DRAFT RunResult，禁止跨 Run 关联。
- 不增加自动执行、AI、权限、云存储或企业协作能力。
- 不开始 Sprint 11，不处理与本 Sprint 无关的依赖漏洞或重构。

---

## 1. Run 可读编号设计

在 `test_runs` 增加 `run_no VARCHAR(20) NOT NULL UNIQUE`，格式固定为 `RUN-000001`。编号全局递增，不复用已删除编号，不包含可变的项目、设备或版本信息；UUID `id` 继续作为内部主键与 API 路径标识。

Repository 提供：

```python
def next_run_no(self) -> str:
    """返回当前数据库下一个 RUN-xxxxxx 编号。"""

def create_run(..., run_no: str, ...) -> TestRun:
    """在原有创建事务中持久化 run_no。"""
```

单机 SQLite 下沿用 Report/Archive 的序号生成策略，并依赖数据库唯一约束兜底。创建普通 Run 和 Focused Regression Run 必须调用同一公共编号生成能力；遇到唯一冲突时回滚整个创建事务并返回 `409`，不留下孤立 Result、Snapshot 或 Focused Regression 关联。

历史回填按 `started_at ASC, id ASC` 确定顺序，从 `RUN-000001` 连续编号。迁移后 `run_no` 不提供更新 API，并增加 ORM 事件阻止已持久化编号变更。

## 2. 历史筛选方案

新增只读分页接口：

`GET /api/test-runs`

查询参数：

| 参数 | 规则 |
|---|---|
| `project_id` | 可选 UUID，精确匹配 |
| `run_no` | 可选，去除首尾空格后不区分大小写的前缀匹配 |
| `project_version` | 可选，精确匹配 TestProject 当前版本 |
| `device_type` | 可选，精确匹配 `device_snapshot.device_type` |
| `vendor` | 可选，不区分大小写的包含匹配 |
| `model` | 可选，不区分大小写的包含匹配 |
| `serial_number` | 可选，不区分大小写的包含匹配 |
| `software_version` | 可选，不区分大小写的包含匹配 |
| `status` | 可选，`IN_PROGRESS` 或 `COMPLETED` |
| `result` | 可选，`PASS`、`FAIL`、`BLOCKED` 或 `UNSET`；匹配至少一个结果 |
| `started_from` / `started_to` | 可选 ISO 8601 日期时间，闭区间 |
| `limit` | 默认 25，范围 1..100 |
| `offset` | 默认 0，最小 0 |

返回：

```json
{
  "items": [
    {
      "id": "uuid",
      "run_no": "RUN-000123",
      "project_id": "uuid",
      "project_name": "ONU Release",
      "project_version": "R2",
      "device": {
        "device_type": "ONU",
        "vendor": "Huawei",
        "model": "HG8245",
        "serial_number": "DUT-001",
        "software_version": "V2"
      },
      "status": "COMPLETED",
      "summary": {"total": 5, "pass": 4, "fail": 1, "blocked": 0, "unset": 0},
      "started_at": "2026-08-11T09:00:00",
      "finished_at": "2026-08-11T10:00:00"
    }
  ],
  "total": 1,
  "limit": 25,
  "offset": 0
}
```

Repository 使用 SQLAlchemy 构造参数化查询；Snapshot 字段通过 SQLite `json_extract` 读取，不做 Python 全表加载。结果按 `started_at DESC, id DESC` 稳定排序。`total` 与 `items` 使用相同过滤谓词，避免分页统计漂移。

## 3. Run 比较方案

新增只读接口：

`POST /api/test-runs/compare`

请求必须包含 2–5 个互不重复的 Run，数组第一项为基线，其余为目标：

```json
{"run_ids": ["base-run-uuid", "target-a-uuid", "target-b-uuid"]}
```

Service 只读取所选 Run 的历史 Snapshot 与锁定结果，不读取当前 Device/TestCase/Profile 数据。用 `case_snapshot.case_code` 对齐结果；同一 Run 内若出现重复 `case_code`，返回 `409`，避免比较歧义。允许不同项目、设备或版本比较，并在响应中明确返回上下文差异。

每个用例行返回 `base` 和按请求顺序排列的 `targets`；每个目标分别带 `change`：

- 相同结果：`UNCHANGED`
- `FAIL/BLOCKED → PASS`：`IMPROVED`
- `PASS → FAIL/BLOCKED`：`REGRESSED`
- `FAIL ↔ BLOCKED` 或任一侧为 `NULL` 且两侧都存在：`CHANGED`
- 仅目标 Run 存在：`ADDED`
- 仅基线 Run 存在：`REMOVED`

响应包含 2–5 个 Run 的 `run_no`、项目、设备、环境快照摘要、结果汇总，以及按 `case_code` 排序的比较行。每侧结果附带 Evidence 数量，但不修改或复制 Evidence。Run 不存在返回 `404`；请求重复或数量错误由 Schema 返回 `422`；重复用例码返回 `409`。

## 4. Evidence 多关联模型

新增 `evidence_run_result_links`：

| 字段 | 类型 / 约束 | 说明 |
|---|---|---|
| `evidence_id` | UUID FK → `evidences.id`, PK, CASCADE | Evidence 元数据与物理文件 |
| `run_result_id` | UUID FK → `run_results.id`, PK, CASCADE | 关联结果 |
| `created_at` | DATETIME NOT NULL | 关联创建时间 |

保留 `evidences.run_result_id` 和现有 exactly-one-owner 约束：它继续表示结果 Evidence 的主归属，Defect Evidence 继续只使用 `defect_id`。迁移把所有已有 `run_result_id IS NOT NULL` 的 Evidence 回填一条 Link；Defect Evidence 不进入关联表。

新批量上传一次接收 1..20 个文件和 1..50 个 `run_result_ids`。所有 Result 必须存在、属于同一 TestRun 且为 DRAFT。第一个请求 Result 作为 `Evidence.run_result_id` 主归属，每个文件只存储一次，并为全部目标 Result 创建 Link。文件元数据、Link 与物理文件写入作为一个补偿式事务处理：数据库失败时删除本次已写文件，任一文件失败时回滚本批次元数据和 Link。

生命周期规则：

- 列表：按 Link 查询，所有关联 Result 均可看到同一 Evidence。
- 下载：继续按 Evidence ID 下载并校验既有元数据。
- 删除：只有该 Evidence 的全部关联 Result 都是 DRAFT 才允许；删除 Evidence 时级联删除 Link，再删除单份物理文件。
- 新增关联：只通过批量上传创建，不提供对已有 Evidence 单独增删 Link 的 API。
- Defect Evidence 生命周期保持 Sprint 5 规则，不允许混合关联 Defect 与多个 Result。

## 5. 数据迁移策略

新增 Alembic revision `20260811_0010_history_evidence_efficiency`，`down_revision="20260810_0009"`。

Upgrade 顺序：

1. 以 SQLite batch 模式给 `test_runs` 增加临时可空 `run_no`。
2. 按 `started_at, id` 读取历史 Run，写入确定性的 `RUN-xxxxxx`。
3. 将 `run_no` 改为 NOT NULL，创建唯一约束 `uq_test_runs_run_no`。
4. 创建 `evidence_run_result_links`、复合主键及 `run_result_id` 索引。
5. 用 `INSERT ... SELECT id, run_result_id, created_at FROM evidences WHERE run_result_id IS NOT NULL` 回填主关联。
6. 验证每条结果 Evidence 恰好至少有一条 Link 后完成迁移。

Downgrade 顺序：删除 Link 表，再使用 batch 模式移除 `run_no`。Downgrade 不删除 Evidence 文件或元数据；降级后额外关联不可表达，因此迁移测试必须明确：仅允许在没有多关联记录时 downgrade，否则抛出可读错误并保持数据库不变。

迁移测试覆盖空库升级、Sprint 9 库升级、确定性回填、唯一/非空约束、外键、级联、`PRAGMA foreign_keys=ON`、安全 downgrade 与失败回滚。

## 6. Archive 兼容方案

新 Report 生成时，ReportRepository 通过 Link 加载 Run 内 Evidence，并在每个关联 Result 的 Snapshot 中记录同一 Evidence 元数据；既有 Report Snapshot 永不回写。`run.run_no` 仅写入新生成的 Snapshot 与 HTML，历史 Report 内容保持原样。

Archive 生成对 `report_snapshot.results[*].evidences` 按 Evidence `id` 去重：

- HTML 中每个关联 Result 都显示 Evidence；
- ZIP 中同一 Evidence 只出现一次，路径仍为 `evidence/{evidence_id}/{original_name}`；
- manifest 中同一 `path` 只出现一次；
- 打包前继续逐文件校验 SHA256 与大小；
- 已生成 Archive 文件和 manifest 不修改。

兼容测试同时使用旧式 Snapshot（无 `run_no`、无重复 Evidence）和新式 Snapshot（一个 Evidence 出现在多个 Result）验证 HTML、SHA256、ZIP 文件名及 manifest。

## 7. API 设计

### 历史与比较

- `GET /api/test-runs`：组合筛选、稳定分页，返回 `RunHistoryPage`。
- `POST /api/test-runs/compare`：比较两个历史 Run，返回 `RunComparisonRead`。
- `GET /api/test-runs/{run_id}`：保持现有详情接口，并新增 `run_no` 字段。
- `GET /api/test-projects/{project_id}/runs`：保持兼容，响应元素新增 `run_no`。

### Evidence

- `POST /api/evidences/batch`：multipart；字段 `run_result_ids` 为重复 form 字段，`files` 为重复文件字段，另含统一 `category` 与可选 `description`；成功返回 `201` 和创建的 Evidence 列表。
- `GET /api/run-results/{result_id}/evidences`：改为通过 Link 返回所有关联 Evidence。
- `DELETE /api/evidences/{evidence_id}`：保持路径，生命周期校验升级为检查全部关联 Result。
- 既有单结果上传 API 保留，并在内部创建主 Link，避免破坏现有前端和 Diagnostic Evidence 录入。

错误规则：资源不存在 `404`；LOCKED、跨 Run、迁移编号冲突或比较歧义 `409`；参数数量、枚举、日期范围、空文件列表 `422`；文件超限 `413`；物理文件缺失 `410`。响应不暴露 `storage_path` 的绝对路径。

## 8. 前端页面设计

在测试执行页中保留项目和 Run 详情流程，新增三个聚焦组件：

1. `RunHistoryPanel`：显示 Run 编号、项目版本、DUT、软件版本、状态和结果汇总；提供项目、编号、设备、版本、状态、结果、日期筛选及分页；筛选提交后请求服务端，不在浏览器全量过滤。
2. `RunComparisonPanel`：从筛选结果勾选 2–5 个 Run，首项作为基线；顶部并排显示 Run/DUT/环境摘要，主体按 Case Code 展示基线与各目标结果并用文本标签标记改进、退化、变化、新增、移除；可跳转各 Run 详情。
3. `BatchEvidencePanel`：仅在活动 Run 有两个或以上 DRAFT Result 时显示；支持多选结果、多文件、统一类别和说明，展示待上传文件数与目标结果数；成功后触发相关 `ResultEditor` 刷新 Evidence 列表。

LOCKED Result 在批量选择器中禁用并显示原因。单结果 Evidence 上传入口继续保留。所有错误沿用页面错误区，不加入后台任务、拖拽目录上传或跨 Run 文件复用。

## 9. 测试策略

- Migration：历史编号顺序、NOT NULL/UNIQUE、Link 回填、外键、级联、安全 downgrade。
- Model：`run_no` 不可修改、复合主键防重复 Link、Evidence 元数据继续不可变。
- Repository：组合筛选、JSON Snapshot 条件、结果存在性过滤、稳定分页、总数一致、批量事务与排序。
- Service：编号冲突回滚、2–5 Run 比较分类、重复 Case Code、跨 Run Evidence 拒绝、全部 DRAFT 门禁、文件补偿清理、全部关联 Result 的删除门禁。
- API：成功响应及 404/409/410/413/422；multipart 多文件/多 Result；既有单上传兼容。
- Frontend：筛选参数、分页、双选限制、比较渲染、批量选择、上传成功刷新、LOCKED 禁用、错误反馈。
- Report/Archive：新 Report 展开多关联，ZIP/manifest 去重，旧 Snapshot 兼容，SHA256 篡改检测保持有效。
- 全量回归：Device、TestCase、TestExecution、Evidence、Defect/Regression、Environment、Report/Archive、Diagnostic、Focused Regression 均保持通过。

## 10. 风险控制

| 风险 | 控制措施 |
|---|---|
| 可读编号并发重复 | 数据库 UNIQUE 兜底；同一事务生成和插入；冲突整体回滚并返回 409 |
| SQLite batch migration 破坏外键 | 空库和 Sprint 9 数据库双路径测试；迁移后检查所有 FK 与行数 |
| 多关联改变 LOCKED 历史 | 创建时要求所有目标 DRAFT；不提供独立 Link 更新 API；任一关联 LOCKED 后禁止删除 |
| 一个文件被重复存储 | 每个上传文件只创建一条 Evidence 和一个 storage path，多 Result 只增加 Link |
| Archive 重复 ZIP 路径 | Snapshot 可重复引用，打包阶段按 Evidence ID 去重并验证 manifest 路径唯一 |
| 跨 Run 证据语义不清 | V1.1 明确禁止跨 Run 关联；跨 Run 请求返回 409 |
| 筛选数据量增长 | SQL 过滤、索引、最大 100 条分页；不在 Python 或前端加载全表 |
| JSON Snapshot 查询性能 | 先以项目、状态、时间等普通列收窄；为单机规模保留 `json_extract`，不引入搜索服务 |
| 比较错误解读 | 固定、可测试的变化矩阵；同时展示原始结果，不生成自动结论 |
| 旧客户端兼容 | 保留既有项目 Run 列表、单上传、下载、删除路径；只增加响应字段和新端点 |

---

### Task 1: Migration contract, Run number, and Evidence links

**Files:**
- Create: `backend/tests/test_history_evidence_migration.py`
- Create: `backend/migrations/versions/20260811_0010_history_evidence_efficiency.py`
- Create: `backend/app/models/evidence_link.py`
- Modify: `backend/app/models/test_execution.py`
- Modify: `backend/app/models/evidence.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Produces: immutable `TestRun.run_no: str` and `EvidenceRunResultLink(evidence_id, run_result_id, created_at)`.
- Consumes: Sprint 9 revision `20260810_0009`, existing RunResult/Evidence foreign keys, and SQLite foreign-key enforcement.

- [ ] **Step 1: Write failing migration tests** for empty upgrade, populated upgrade, deterministic `run_no` backfill, NOT NULL/UNIQUE, Link backfill, composite uniqueness, cascades, safe downgrade, and rollback.
- [ ] **Step 2: Run the migration test and verify RED.**

  Run: `python -m pytest backend/tests/test_history_evidence_migration.py -q`

  Expected: FAIL because revision `20260811_0010` does not exist.

- [ ] **Step 3: Implement the Alembic revision** in the exact upgrade/downgrade order from section 5.
- [ ] **Step 4: Write failing ORM tests** proving persisted `run_no` cannot change and duplicate Evidence/Result Links are rejected.
- [ ] **Step 5: Implement ORM fields, relationships, and immutability listener** without changing Snapshot or LOCKED Result listeners.
- [ ] **Step 6: Run focused migration/model tests and verify GREEN.**

  Run: `python -m pytest backend/tests/test_history_evidence_migration.py backend/tests/test_test_execution_repository.py backend/tests/test_evidence_repository.py -q`

  Expected: PASS.

- [ ] **Step 7: Commit.**

  ```powershell
  git add backend/app/models backend/migrations/versions/20260811_0010_history_evidence_efficiency.py backend/tests/test_history_evidence_migration.py backend/tests/test_test_execution_repository.py backend/tests/test_evidence_repository.py
  git commit -m "feat(history): add run numbers and evidence links"
  ```

### Task 2: Shared Run number allocation

**Files:**
- Create: `backend/app/test_execution/run_numbers.py`
- Create: `backend/tests/test_run_numbers.py`
- Modify: `backend/app/test_execution/repository.py`
- Modify: `backend/app/test_execution/service.py`
- Modify: `backend/app/focused_regressions/repository.py`
- Modify: `backend/app/focused_regressions/service.py`
- Modify: `backend/app/test_execution/schemas.py`

**Interfaces:**
- Produces: `RunNumberAllocator.next(repository) -> str` and `run_no` in every TestRun response.
- Consumes: one SQLAlchemy Session per ordinary or Focused Regression Run creation transaction.

- [ ] **Step 1: Write failing tests** for empty sequence, existing/gapped numbers, malformed legacy values, ordinary Run assignment, Focused Regression assignment, conflict rollback, and immutability.
- [ ] **Step 2: Run tests and verify RED.**

  Run: `python -m pytest backend/tests/test_run_numbers.py backend/tests/test_test_execution_service.py backend/tests/test_focused_regression_service.py -q`

  Expected: FAIL because new Run creation does not assign `run_no`.

- [ ] **Step 3: Implement the shared allocator** with `RUN-` prefix and six-digit padding, using the transaction's Session.
- [ ] **Step 4: Integrate the allocator** into both Run creation paths before flush/commit; translate unique conflicts into the existing conflict response layer.
- [ ] **Step 5: Add `run_no` to TestRun schemas** without changing UUID routes.
- [ ] **Step 6: Run focused tests and verify GREEN.**

  Run: `python -m pytest backend/tests/test_run_numbers.py backend/tests/test_test_execution_service.py backend/tests/test_focused_regression_service.py backend/tests/test_test_execution_api.py backend/tests/test_focused_regression_api.py -q`

  Expected: PASS.

- [ ] **Step 7: Commit.**

  ```powershell
  git add backend/app/test_execution backend/app/focused_regressions backend/tests/test_run_numbers.py backend/tests/test_test_execution_service.py backend/tests/test_focused_regression_service.py backend/tests/test_test_execution_api.py backend/tests/test_focused_regression_api.py
  git commit -m "feat(history): assign readable run numbers"
  ```

### Task 3: Filtered Run history repository and API

**Files:**
- Create: `backend/app/run_history/__init__.py`
- Create: `backend/app/run_history/repository.py`
- Create: `backend/app/run_history/service.py`
- Create: `backend/app/run_history/schemas.py`
- Create: `backend/app/run_history/router.py`
- Create: `backend/tests/test_run_history_repository.py`
- Create: `backend/tests/test_run_history_service.py`
- Create: `backend/tests/test_run_history_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: `RunHistoryFilters`, `RunHistoryPage`, `RunHistoryRepository.search(filters)`, and `GET /api/test-runs`.
- Consumes: immutable TestRun/RunResult Snapshot fields and current TestProject name/version for list context.

- [ ] **Step 1: Write failing repository tests** for every filter, combined predicates, `UNSET`, inclusive dates, stable sort, limit/offset, and matching totals.
- [ ] **Step 2: Write failing service/API tests** for defaults, whitespace normalization, enum/date validation, empty pages, and response summaries.
- [ ] **Step 3: Run tests and verify RED.**

  Run: `python -m pytest backend/tests/test_run_history_repository.py backend/tests/test_run_history_service.py backend/tests/test_run_history_api.py -q`

  Expected: FAIL because the `run_history` package is absent.

- [ ] **Step 4: Implement parameterized SQLAlchemy filtering** with SQLite JSON extraction and grouped result counts.
- [ ] **Step 5: Implement Service and Router** with no write methods and register the Router under `/api`.
- [ ] **Step 6: Run focused tests and verify GREEN.**

  Run: `python -m pytest backend/tests/test_run_history_repository.py backend/tests/test_run_history_service.py backend/tests/test_run_history_api.py -q`

  Expected: PASS.

- [ ] **Step 7: Commit.**

  ```powershell
  git add backend/app/run_history backend/app/main.py backend/tests/test_run_history_repository.py backend/tests/test_run_history_service.py backend/tests/test_run_history_api.py
  git commit -m "feat(history): add filtered run history"
  ```

### Task 4: Snapshot-based Run comparison

**Files:**
- Create: `backend/app/run_history/comparison.py`
- Create: `backend/tests/test_run_comparison.py`
- Modify: `backend/app/run_history/repository.py`
- Modify: `backend/app/run_history/service.py`
- Modify: `backend/app/run_history/schemas.py`
- Modify: `backend/app/run_history/router.py`

**Interfaces:**
- Produces: `compare_runs(base, target, evidence_counts) -> RunComparisonRead` and `POST /api/test-runs/compare`.
- Consumes: two TestRun graphs, historical case/device/environment Snapshots, and Evidence Link counts.

- [ ] **Step 1: Write failing comparison tests** for 2–5 Run ordering, all seven change labels per target, stable Case Code ordering, focused Run subsets, different devices/environments, duplicate Case Code conflict, missing Run, and zero source mutation.
- [ ] **Step 2: Write failing API tests** for 2-Run and 5-Run comparison, duplicate IDs, fewer than 2, more than 5, 404, 409, and 422.
- [ ] **Step 3: Run tests and verify RED.**

  Run: `python -m pytest backend/tests/test_run_comparison.py backend/tests/test_run_history_api.py -q`

  Expected: FAIL because comparison behavior is absent.

- [ ] **Step 4: Implement pure comparison logic** using deep-read Snapshot values and the classification matrix from section 3.
- [ ] **Step 5: Add repository graph/evidence-count queries and expose the endpoint** without adding update or delete operations.
- [ ] **Step 6: Run focused tests and verify GREEN.**

  Run: `python -m pytest backend/tests/test_run_comparison.py backend/tests/test_run_history_api.py -q`

  Expected: PASS.

- [ ] **Step 7: Commit.**

  ```powershell
  git add backend/app/run_history backend/tests/test_run_comparison.py backend/tests/test_run_history_api.py
  git commit -m "feat(history): compare historical run results"
  ```

### Task 5: Evidence links and batch upload service

**Files:**
- Create: `backend/tests/test_evidence_batch_service.py`
- Modify: `backend/app/evidence/repository.py`
- Modify: `backend/app/evidence/service.py`
- Modify: `backend/app/evidence/schemas.py`
- Modify: `backend/tests/test_evidence_repository.py`
- Modify: `backend/tests/test_evidence_service.py`

**Interfaces:**
- Produces: `EvidenceService.create_batch_for_results(result_ids, files, category, description) -> list[Evidence]` and Link-aware list/delete operations.
- Consumes: existing `EvidenceStorage.store/delete`, per-file size limit, and SQLAlchemy transaction Session.

- [ ] **Step 1: Write failing repository tests** for Link backfill semantics, Link-aware listing, deterministic ordering, duplicate suppression, all-owner loading, and cascade deletion.
- [ ] **Step 2: Write failing service tests** for 1..20 files, 1..50 unique results, same-Run validation, all-DRAFT validation, shared storage path, one Link per target, LOCKED delete denial, and cleanup after file/DB failure.
- [ ] **Step 3: Run tests and verify RED.**

  Run: `python -m pytest backend/tests/test_evidence_repository.py backend/tests/test_evidence_service.py backend/tests/test_evidence_batch_service.py -q`

  Expected: FAIL because Link-aware batch operations are absent.

- [ ] **Step 4: Refactor Repository transaction boundaries** so Service can stage multiple Evidence/Links and commit once; preserve single-upload behavior through the same primitives.
- [ ] **Step 5: Implement batch validation and compensation cleanup** without changing Defect Evidence rules.
- [ ] **Step 6: Run focused tests and verify GREEN.**

  Run: `python -m pytest backend/tests/test_evidence_repository.py backend/tests/test_evidence_service.py backend/tests/test_evidence_batch_service.py backend/tests/test_diagnostic_evidence.py -q`

  Expected: PASS, including Diagnostic single-Evidence compatibility.

- [ ] **Step 7: Commit.**

  ```powershell
  git add backend/app/evidence backend/tests/test_evidence_repository.py backend/tests/test_evidence_service.py backend/tests/test_evidence_batch_service.py backend/tests/test_diagnostic_evidence.py
  git commit -m "feat(evidence): support multi-result batch evidence"
  ```

### Task 6: Evidence batch API compatibility

**Files:**
- Modify: `backend/app/evidence/router.py`
- Modify: `backend/app/evidence/schemas.py`
- Modify: `backend/tests/test_evidence_api.py`

**Interfaces:**
- Produces: `POST /api/evidences/batch`, extended `EvidenceRead.run_result_ids`, and unchanged single-result/Defect endpoints.
- Consumes: `EvidenceService.create_batch_for_results` and stable exception-to-HTTP mappings.

- [ ] **Step 1: Write failing API tests** for repeated multipart result/file fields, ordered response, same-Run success, 404, 409, 413, 422, and single-upload Link creation.
- [ ] **Step 2: Run tests and verify RED.**

  Run: `python -m pytest backend/tests/test_evidence_api.py -q`

  Expected: FAIL because batch route and multi-owner response are absent.

- [ ] **Step 3: Implement multipart parsing and response serialization**; sanitize every filename and return IDs instead of absolute storage paths.
- [ ] **Step 4: Preserve existing API contracts** for Defect upload, download, deletion, and single RunResult upload.
- [ ] **Step 5: Run Evidence and Diagnostic API tests.**

  Run: `python -m pytest backend/tests/test_evidence_api.py backend/tests/test_diagnostic_api.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit.**

  ```powershell
  git add backend/app/evidence/router.py backend/app/evidence/schemas.py backend/tests/test_evidence_api.py backend/tests/test_diagnostic_api.py
  git commit -m "feat(evidence): expose batch evidence api"
  ```

### Task 7: Report and Archive compatibility

**Files:**
- Modify: `backend/app/reports/repository.py`
- Modify: `backend/app/reports/snapshots.py`
- Modify: `backend/app/reports/service.py`
- Modify: `backend/app/reports/renderer.py`
- Modify: `backend/tests/test_report_repository.py`
- Modify: `backend/tests/test_report_snapshot.py`
- Modify: `backend/tests/test_report_service.py`
- Modify: `backend/tests/test_report_storage.py`

**Interfaces:**
- Produces: Link-aware Evidence expansion, `run_no` in new Report Snapshots, and ID-deduplicated archive manifests.
- Consumes: immutable Report Snapshot JSON and existing SHA256-verified artifact storage.

- [ ] **Step 1: Write failing tests** for one shared Evidence under two Results, one ZIP member/manifest entry, old Snapshot compatibility, `run_no` rendering, missing file, and hash mismatch.
- [ ] **Step 2: Run tests and verify RED.**

  Run: `python -m pytest backend/tests/test_report_repository.py backend/tests/test_report_snapshot.py backend/tests/test_report_service.py backend/tests/test_report_storage.py -q`

  Expected: FAIL because reports only follow primary `run_result_id` and archives do not deduplicate repeated IDs.

- [ ] **Step 3: Implement Link-aware repository/snapshot mapping** while keeping Defect Evidence handling unchanged.
- [ ] **Step 4: Deduplicate archive Evidence by ID before manifest creation** and reject conflicting metadata for the same ID.
- [ ] **Step 5: Render `run_no` only when present** so old Snapshot rendering remains valid.
- [ ] **Step 6: Run Report/Archive tests and verify GREEN.**

  Run: `python -m pytest backend/tests/test_report_repository.py backend/tests/test_report_snapshot.py backend/tests/test_report_service.py backend/tests/test_report_storage.py backend/tests/test_report_api.py -q`

  Expected: PASS.

- [ ] **Step 7: Commit.**

  ```powershell
  git add backend/app/reports backend/tests/test_report_repository.py backend/tests/test_report_snapshot.py backend/tests/test_report_service.py backend/tests/test_report_storage.py backend/tests/test_report_api.py
  git commit -m "fix(report): support shared evidence archives"
  ```

### Task 8: Frontend Run history and comparison

**Files:**
- Create: `frontend/src/runHistory/types.ts`
- Create: `frontend/src/runHistory/api.ts`
- Create: `frontend/src/runHistory/api.test.ts`
- Create: `frontend/src/runHistory/RunHistoryPanel.tsx`
- Create: `frontend/src/runHistory/RunHistoryPanel.test.tsx`
- Create: `frontend/src/runHistory/RunComparisonPanel.tsx`
- Create: `frontend/src/runHistory/RunComparisonPanel.test.tsx`
- Modify: `frontend/src/testExecution/TestExecutionPage.tsx`
- Modify: `frontend/src/testExecution/TestExecutionPage.test.tsx`
- Modify: `frontend/src/testExecution/types.ts`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Produces: `RunHistoryApi.search(filters)`, `compare(runIds)`, `RunHistoryPanel`, and `RunComparisonPanel`.
- Consumes: `run_no`, paged summaries, comparison response, and existing `openRun(runId)` navigation.

- [ ] **Step 1: Write failing API tests** for query encoding, omitted empty filters, pagination, comparison POST, and error detail propagation.
- [ ] **Step 2: Write failing component tests** for filter submission/reset, Run numbers, pagination, exactly-two selection, comparison labels, detail navigation, loading, empty, and error states.
- [ ] **Step 3: Run frontend tests and verify RED.**

  Run: `npm.cmd test -- --reporter=dot --maxWorkers=1 frontend/src/runHistory frontend/src/testExecution/TestExecutionPage.test.tsx`

  Expected: FAIL because Run history components are absent.

- [ ] **Step 4: Implement typed API, filter panel, results table, and comparison panel** without client-side full-history filtering.
- [ ] **Step 5: Replace the UUID-only history list** with `RunHistoryPanel`; retain UUID only in accessible detail text and internal navigation.
- [ ] **Step 6: Run focused frontend tests and verify GREEN.**

  Run: `npm.cmd test -- --reporter=dot --maxWorkers=1 frontend/src/runHistory frontend/src/testExecution/TestExecutionPage.test.tsx`

  Expected: PASS.

- [ ] **Step 7: Commit.**

  ```powershell
  git add frontend/src/runHistory frontend/src/testExecution/TestExecutionPage.tsx frontend/src/testExecution/TestExecutionPage.test.tsx frontend/src/testExecution/types.ts frontend/src/index.css
  git commit -m "feat(history): add run filtering and comparison ui"
  ```

### Task 9: Frontend batch Evidence workflow

**Files:**
- Create: `frontend/src/evidenceBatch/types.ts`
- Create: `frontend/src/evidenceBatch/api.ts`
- Create: `frontend/src/evidenceBatch/api.test.ts`
- Create: `frontend/src/evidenceBatch/BatchEvidencePanel.tsx`
- Create: `frontend/src/evidenceBatch/BatchEvidencePanel.test.tsx`
- Modify: `frontend/src/testExecution/TestExecutionPage.tsx`
- Modify: `frontend/src/testExecution/ResultEditor.tsx`
- Modify: `frontend/src/testExecution/ResultEditor.test.tsx`
- Modify: `frontend/src/testExecution/types.ts`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Produces: `EvidenceBatchApi.upload`, `BatchEvidencePanel`, and an Evidence refresh revision passed to affected ResultEditor instances.
- Consumes: active Run results, DRAFT/LOCKED status, existing Evidence list/download/delete API.

- [ ] **Step 1: Write failing API tests** for repeated `run_result_ids`, multiple `files`, category/description, response parsing, and errors.
- [ ] **Step 2: Write failing component tests** for multi-result selection, LOCKED disabled state, multi-file selection, limits, submit state, success reset, affected-result refresh, and error feedback.
- [ ] **Step 3: Run frontend tests and verify RED.**

  Run: `npm.cmd test -- --reporter=dot --maxWorkers=1 frontend/src/evidenceBatch frontend/src/testExecution/ResultEditor.test.tsx frontend/src/testExecution/TestExecutionPage.test.tsx`

  Expected: FAIL because batch Evidence UI is absent.

- [ ] **Step 4: Implement typed multipart client and panel** with explicit file/result counts and no directory upload.
- [ ] **Step 5: Mount the panel in active Run detail** and increment a refresh token only for successful uploads; ResultEditor reloads its Link-aware Evidence list when the token changes.
- [ ] **Step 6: Run focused frontend tests and verify GREEN.**

  Run: `npm.cmd test -- --reporter=dot --maxWorkers=1 frontend/src/evidenceBatch frontend/src/testExecution/ResultEditor.test.tsx frontend/src/testExecution/TestExecutionPage.test.tsx`

  Expected: PASS.

- [ ] **Step 7: Commit.**

  ```powershell
  git add frontend/src/evidenceBatch frontend/src/testExecution/TestExecutionPage.tsx frontend/src/testExecution/ResultEditor.tsx frontend/src/testExecution/ResultEditor.test.tsx frontend/src/testExecution/TestExecutionPage.test.tsx frontend/src/testExecution/types.ts frontend/src/index.css
  git commit -m "feat(evidence): add batch association ui"
  ```

### Task 10: Documentation and full validation

**Files:**
- Modify: `README.md`
- Modify: `docs/API.md`
- Modify: `docs/DATABASE.md`
- Modify: `docs/ARCHITECTURE.md`
- Create: `docs/SPRINT_10_HISTORY_EVIDENCE_EFFICIENCY.md`

**Interfaces:**
- Produces: operator-facing Run search/compare/Evidence instructions, migration description, API contracts, compatibility notes, and acceptance evidence.
- Consumes: final contracts from Tasks 1–9.

- [ ] **Step 1: Document Run number semantics, filter fields, comparison matrix, batch limits, DRAFT/LOCKED rules, and Archive deduplication.**
- [ ] **Step 2: Run migration verification.**

  Run: `python -m pytest backend/tests/test_history_evidence_migration.py -q`

  Expected: PASS for empty and populated database paths.

- [ ] **Step 3: Run all backend tests.**

  Run: `python -m pytest backend/tests -q`

  Expected: all tests pass with zero failures.

- [ ] **Step 4: Run all frontend tests with bounded workers.**

  Run: `npm.cmd test -- --reporter=dot --maxWorkers=1`

  Expected: all tests pass with zero failures.

- [ ] **Step 5: Run production build.**

  Run: `npm.cmd run build`

  Expected: TypeScript and Vite build succeed.

- [ ] **Step 6: Verify repository scope.**

  Run: `git diff --check` and `git status --short`

  Expected: no database, Evidence, ZIP, `node_modules`, `dist`, cache, credentials, or temporary files are tracked.

- [ ] **Step 7: Commit documentation.**

  ```powershell
  git add README.md docs/API.md docs/DATABASE.md docs/ARCHITECTURE.md docs/SPRINT_10_HISTORY_EVIDENCE_EFFICIENCY.md
  git commit -m "docs: document sprint 10 history efficiency"
  ```

## Acceptance Criteria

1. 每个历史和新 TestRun 都有唯一、稳定、不可修改的 `RUN-xxxxxx` 编号。
2. 普通 Run 与 Focused Regression Run 使用同一编号序列，UUID 路由继续有效。
3. 用户可按项目、编号、DUT、软件版本、状态、结果和日期组合筛选并分页。
4. 用户可选择两个 Run，按 Case Code 查看结果、Snapshot 上下文和确定性变化标签。
5. 比较只读历史 Snapshot，不修改旧 Run、Result 或任何 Snapshot。
6. 一次可上传 1..20 个文件并关联同一 Run 内 1..50 个 DRAFT Result；每个文件仅存储一次。
7. 跨 Run、LOCKED Result 或不存在 Result 的批量关联被拒绝，不留下元数据、Link 或文件残留。
8. 单 Result 上传、Diagnostic Evidence、Defect Evidence、下载和删除接口继续兼容。
9. 新 Report 正确展示共享 Evidence；Archive ZIP/manifest 对同一 Evidence 只收录一次并继续校验 SHA256。
10. 历史 Report/Archive 内容不漂移，Sprint 1–9 全量测试与前端生产构建通过。

## Plan Self-Review

- 需求覆盖：可读编号、历史筛选、双 Run 比较、Evidence 多关联、迁移、Archive、API、前端、测试和风险均映射到独立任务。
- 历史完整性：所有新增写操作只作用于新编号、DRAFT Evidence 及新 Link；不提供历史 Snapshot 或 LOCKED Result 写入口。
- 兼容性：保留 UUID、旧列表接口、单上传及 Defect/Diagnostic Evidence；Report/Archive 只在新生成流程读取 Link。
- 类型一致：全文统一使用 `run_no`、`EvidenceRunResultLink`、`run_result_ids`、`RunHistoryPage` 和七种比较标签。
- 范围检查：未加入统计看板、跨 Run Evidence、自动化执行、AI、权限、云存储或 Sprint 11 内容。
- 完整性检查：每个任务均给出具体文件、接口、RED/GREEN 命令、预期结果和提交边界。
