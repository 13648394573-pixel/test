# Changelog

## 2026-10-10 — 项目进度同步

- 新增 PROJECT_PROGRESS.md，核对 main baae7b2 的平台、Runner 与现场检查进度。
- 修正 README 阶段说明，标注 ROADMAP 的历史适用范围。
- 明确正式 Skill 待验收事项和旧 worktree 未提交状态。
- 本次仅更新文档，未重新执行产品测试或真实设备验收。

## V1 Release Preparation

- 准备日期：2026-08-08
- 候选版本：`v1.0.0-rc1`（尚未创建Tag）
- Beta PASS基线：`5e362687a3a89ee5b4336c9a1db68105858ea875`
- 状态：功能范围冻结，进入正式发布前收尾

完成事项：

- 真实目标ONU完成online、O5、IPoE、PPPoE和网络连通PASS闭环
- `BETA-ISSUE-001`关闭，关联Defect经PASS Regression关闭
- SQLite、Evidence、Report和Archive备份/恢复演练通过
- 空SQLite数据库连续执行7个Alembic迁移至`20260730_0007`
- README、Architecture、Database和API文档同步至Sprint 0–7真实实现
- 新增V1 Release Checklist，记录RC1门禁、观察项和技术债

本阶段未新增业务模块、未修改数据库设计、未扩展V1范围，且未创建Tag。

## V1 Alpha Feature Complete

- 完成时间：2026-07-30
- 基线分支：`main`
- Feature Complete Commit：`edc26db330f57e01e192acd7f2c7260fecf9c747`
- 状态：Sprint 0–7已完成，进入V1 Alpha最终验收与Beta验证阶段

完成能力：

- Device Library、Test Case Library、Test Execution
- Defect & Regression、Test Evidence & Result Integrity
- Environment Snapshot、Report & Archive
- 后端117项测试通过，前端39项测试通过，生产构建通过

当前版本仍保持个人、本地、手工测试定位，不包含AI、多用户协作、自动化执行或云端部署。

本文件记录 Test Workbench 已完成并进入 `main` 的开发基线。

## V1 Reality Review

- 评审时间：2026-07-30
- 评审基线：`6f60601c9e535c49efae93bb0476cca005b5b1ee`
- 当前版本定义：**V1 Alpha**

评审结论：

- Device Library、Test Case Library、Test Execution、Defect & Regression 已形成核心测试记录闭环。
- 当前版本尚缺测试证据、环境快照、报告与归档能力，因此不是完整 V1。
- 后续路线调整为 Sprint 5「Test Evidence & Result Integrity」、Sprint 6「Environment Snapshot」、Sprint 7「Report & Archive」。
- V1 继续保持个人、本地、手工测试定位，不扩展 AI、多用户、企业协作或自动化执行。

## Sprint 1 — Device Library

- 完成时间：2026-07-29
- 状态：完成并合并到 `main`
- Commit：`04f712d01ffe9e481985f856ca4ed70781525ab6`

完成内容：

- Device 数据模型与 Alembic 迁移
- Repository、Service 和 CRUD API
- 设备列表、新建、编辑和删除页面
- 后端、前端及浏览器 E2E 验证

## Sprint 0 — Foundation

- 状态：完成

完成内容：

- React/Vite 基础工程
- FastAPI 基础工程
- SQLite 与 SQLAlchemy 配置
- 配置管理、日志和开发说明
