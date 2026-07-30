# Changelog

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
