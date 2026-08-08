# Test Workbench V1 Release Checklist

## 候选版本

| 项目 | 当前值 |
|---|---|
| 候选Tag | `v1.0.0-rc1`（准备中，尚未创建） |
| 分支 | `main` |
| Feature Complete | `edc26db330f57e01e192acd7f2c7260fecf9c747` |
| Beta PASS基线 | `5e362687a3a89ee5b4336c9a1db68105858ea875` |
| 产品范围 | 单用户、本地、手工网络设备测试记录闭环 |

## 1. 功能范围

- [x] Sprint 0 Foundation
- [x] Sprint 1 Device Library
- [x] Sprint 2 Test Case Library
- [x] Sprint 3 Test Execution
- [x] Sprint 4 Defect & Regression
- [x] Sprint 5 Test Evidence & Result Integrity
- [x] Sprint 6 Environment Snapshot
- [x] Sprint 7 Report & Archive
- [x] 未引入AI、多用户、企业协作、自动化执行、云存储或复杂工作流

## 2. Beta验收

- [x] 创建独立真实DUT TestRun，保留历史Run和Snapshot
- [x] ONU online PASS
- [x] O5 PASS
- [x] IPoE PASS
- [x] PPPoE PASS
- [x] 网络连通PASS：4/4、0%丢包
- [x] 3项RunResult全部PASS/LOCKED
- [x] PASS Regression关闭`DEF-000001`
- [x] 生成`RPT-000003`与`ARC-000003`并校验SHA256
- [x] `BETA-ISSUE-001`状态CLOSED

详细记录：[Beta Execution Record](V1_BETA_EXECUTION_RECORD.md)和[Beta Issue Log](V1_BETA_ISSUE_LOG.md)。

## 3. 数据与迁移

- [x] SQLite、Evidence、Report、Archive完成备份/恢复演练
- [x] 源、备份、恢复24/24文件SHA256一致
- [x] 恢复SQLite quick_check通过且无外键违规
- [x] 恢复后22/22文件可通过现有API下载并匹配SHA256
- [x] 空数据库从base连续升级至`20260730_0007`
- [x] 空库16张表、quick_check和外键检查通过
- [ ] 正式Tag前将发布备份复制到工作区之外的独立介质

详细记录：[Backup / Restore Drill](V1_BACKUP_RESTORE_DRILL.md)和[Empty Database Migration Validation](V1_EMPTY_DATABASE_MIGRATION_VALIDATION.md)。

## 4. 自动验证

- [x] 发布准备最终后端测试：117 passed
- [x] 发布准备最终前端测试：39 passed，使用`--maxWorkers=1`
- [x] 发布准备最终生产构建通过
- [x] `git diff --check`通过
- [x] Git只包含计划内文档，无数据库、附件、ZIP、dist、缓存或临时文件
- [ ] `main`工作区干净

## 5. 文档

- [x] README已覆盖Sprint 0–7、配置、迁移、启动和验证
- [x] ARCHITECTURE已覆盖前后端、分层、数据流和不可变规则
- [x] DATABASE已覆盖15张业务表、关系、迁移和备份要求
- [x] API已覆盖全部当前Router和错误规则
- [x] Beta PASS、Issue关闭、备份恢复和空库迁移已有记录
- [x] CHANGELOG已进入V1 Release Preparation

## 6. 已知技术债与观察项

以下项目不否定本次业务PASS，但必须在创建Tag前由发布人明确接受：

- [ ] OLT显示`Config state=failed`，同时`Match state=match`且O5、IPoE、PPPoE和网络连通均实际通过。
- [ ] SN认证场景下ONU Web显示`LOID Error`；本轮未使用LOID认证。
- [ ] 历史Beta文件跨两个存储根；恢复已通过hash驱动人工归一化，正式数据库生命周期必须固定存储根。
- [ ] Alembic CLI不会自动读取`TEST_WORKBENCH_DATABASE_URL`切换目标；自定义目标需显式覆盖Config URL。
- [ ] 当前只有人工备份/恢复流程，没有自动备份工具。
- [ ] Beta规模仍以少量用例和单一真实ONU闭环为主，100+用例、大附件及更多型号作为后续非阻断验证。

## 7. 安全与范围

- [x] 确认`.env`及测试凭据未被Git跟踪
- [x] 确认数据库、Evidence、Report、Archive、备份和日志未被Git跟踪
- [x] 确认文档中的完整SN、MAC、管理地址和账号已脱敏
- [x] 确认未新增业务模块、依赖、迁移或架构变更

## 8. RC1 Tag门禁

只有以下条件全部满足后才能创建`v1.0.0-rc1`：

1. 本清单第4、6、7节由发布人复核完成。
2. Release Preparation文档提交位于`main`且工作区干净。
3. 正式发布备份已复制到工作区之外。
4. 后端、前端和生产构建使用发布提交重新验证通过。
5. 人工接受所有非阻断观察项。

建议Tag命令（本阶段不执行）：

```powershell
git tag -a v1.0.0-rc1 -m "Test Workbench v1.0.0-rc1"
```

## 最终签署

| 角色 | 姓名 | 日期 | 结论 |
|---|---|---|---|
| 测试工程师 | __________ | __________ | PASS / HOLD |
| 发布复核 | __________ | __________ | APPROVED / REJECTED |
