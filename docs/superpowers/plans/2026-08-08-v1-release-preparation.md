# V1 Release Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 Test Workbench V1 正式发布前的验收固化、恢复演练、迁移验证、文档同步和 RC1 检查，不新增功能。

**Architecture:** 保持现有 React + FastAPI + SQLite 单机 B/S 架构不变。运行数据演练仅使用 Git 忽略的 `data/` 目录，所有可审计结论写入 `docs/`，不修改业务代码、ORM或迁移。

**Tech Stack:** Git、PowerShell、Python 3.12、SQLite、Alembic、Pytest、Vitest、Vite。

## Global Constraints

- 不新增业务模块，不启动Sprint。
- 不改变数据库设计，不扩展V1范围。
- 不创建正式Tag；仅准备`v1.0.0-rc1`。
- 历史Run、Snapshot、LOCKED Result、Report和Archive不可修改。

---

### Task 1: 固化 Beta PASS 基线

**Files:**
- Modify: `docs/V1_BETA_EXECUTION_RECORD.md`
- Modify: `docs/V1_BETA_ISSUE_LOG.md`

- [ ] 核对专项恢复Run、Evidence、Regression、Report和Archive标识。
- [ ] 核对`BETA-ISSUE-001`关闭与Release观察项。
- [ ] 确认Git变更仅包含两份Beta文档并创建单一提交。

### Task 2: 备份与恢复演练

**Files:**
- Create: `docs/V1_BACKUP_RESTORE_DRILL.md`
- Runtime only: `data/release-prep-backup-20260808/`
- Runtime only: `data/release-prep-restore-20260808/`

- [ ] 备份独立Beta SQLite数据库、Evidence和Report/Archive文件。
- [ ] 生成源文件与备份文件SHA256清单并逐项比较。
- [ ] 从备份恢复到独立目录，执行SQLite quick_check、对象计数和文件hash复核。
- [ ] 记录命令、范围、结果、限制和恢复结论。

### Task 3: 空数据库迁移验证

**Files:**
- Create: `docs/V1_EMPTY_DATABASE_MIGRATION_VALIDATION.md`
- Runtime only: `data/release-prep-empty-migration-20260808.db`

- [ ] 对独立空数据库执行`alembic upgrade head`。
- [ ] 核对Alembic版本、业务表、外键和SQLite quick_check。
- [ ] 记录迁移命令和验证结果。

### Task 4: 核心文档同步

**Files:**
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/DATABASE.md`
- Modify: `docs/API.md`

- [ ] 按Sprint 0–7当前代码更新模块、目录、配置、启动和验证说明。
- [ ] 按实际ORM和迁移更新表结构、关系、不变性及迁移方法。
- [ ] 按实际Router更新全部API、状态码和返回规则。
- [ ] 核对文档不包含凭据、真实完整DUT标识或运行时文件。

### Task 5: RC1发布检查

**Files:**
- Create: `docs/V1_RELEASE_CHECKLIST.md`
- Modify: `docs/CHANGELOG.md`

- [ ] 汇总Sprint 0–7、Beta、备份恢复和空库迁移结果。
- [ ] 明确阻断项、观察项、已知技术债和Tag前操作。
- [ ] 将候选版本标记为`v1.0.0-rc1`准备中，不创建Tag。

### Task 6: 最终验证与版本固化

**Files:**
- Test: `backend/tests/`
- Test: `frontend/src/**/*.test.*`

- [ ] 运行后端全量测试并确认117项通过。
- [ ] 运行前端单worker测试并确认39项通过。
- [ ] 执行生产构建并确认成功。
- [ ] 执行`git diff --check`、敏感文件和运行时产物检查。
- [ ] 创建发布准备文档提交，保留`v1.0.0-rc1` Tag待用户批准。
