# Changelog

## 2026-10-29 — 归档路径对齐、缺陷字段保护与报告双模式

- Report Archive：ZIP 内 evidence 路径改为与数据库 `evidences.storage_path` 一致（`evidence/<storage_path>`），manifest `files[]` 增加 `original_name`，消除"zip 内 UUID 与磁盘目录对不上"的追溯断点。
- Defects：`update_defect` 禁止直接修改受保护字段（status、resolved_at、closed_at、defect_code、source_run_result_id 等），修复创建时即写入 `resolved_at` 导致时间线失真的通道；回归 PASS 关闭缺陷时若 `resolved_at` 为空则兜底回填。
- Reports：新增双模式报告模板（`formal` 客户验收版含签字栏/文档信息，`internal` 内部存档版含执行时间、RunResult ID 等技术细节），API `POST /test-runs/{id}/reports` 增加 `mode` 参数，前端报告页增加模式选择。
- 历史数据订正（v1_beta_round1.db）：`DEF-000001.resolved_at` 由创建时刻订正为回归 PASS 时间（2026-08-08 02:57:27.347193），原值与订正原因保留在 `resolution_notes` 前缀 `[CORRECTED 2026-10-29]` 中。
- 新增后端测试：`tests/test_report_renderer.py`、缺陷受保护字段用例；更新 `tests/test_report_storage.py` 与前端 report 测试。

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

## 2026-10-29（2）— 报告版面按客户验收要求调整

- 报告正文不再展示测试环境；页眉改为"版本号 + 客户代码"（API 与前端新增 `customer_code` 字段），测试设备/环境信息在用例说明中体现（结果表显示用例 description）。
- 截图证据内嵌：生成报告时将 image 类证据以 base64（SHA256 校验后）内嵌为缩略图，点击可查看原图，HTML 报告自包含，适合直接交付客户。
- internal 模式文档信息中保留环境快照名称与版本一行，便于内部追溯。

## 2026-10-29（3）— 证据自动解析、凭据安全、PDF 导出与用例库扩充

- Evidence：新增 `parsed_metadata` 列（迁移 `20261029_0022`），上传文本证据时自动解析 OLT CLI/PON 状态/ping 诊断并存储结构化元数据与自动判定结果；报告证据栏显示判定徽章（ONT 在线/O5/光功率/丢包/时延）。
- Environments：环境参数支持 `credential:<引用名>` 引用 keyring 凭据，快照自动脱敏为 `***`；模型层拒绝含 password/secret 等键名的明文值。
- Reports：新增 `POST /reports/{id}/pdf` 与 `GET /reports/{id}/pdf`，经 SHA256 校验的 HTML 用 headless Chromium 打印为 PDF。
- Seeds：`seeds/round2_cases.json` + `tools/seed_test_cases.py`，7 个新用例（异常恢复/光功率边界/PPPoE 重拨/WLAN/TR069），绑定 device_type 不绑定型号。
- Docs：新增 `BETA_ROUND2_TEST_PLAN.md` 与 `DEVICE_MODEL_PORTABILITY.md`。

## 2026-10-29（4）— 移除 PDF 导出

- 按产品决策移除 `POST/GET /reports/{id}/pdf` 与相关服务/存储/异常处理代码；报告交付以自包含 HTML 为准。PDF 导出如有需要后续再议。

## 2026-10-29（5）— 端到端冒烟验证与修复

- 新增 `backend/scripts/smoke_e2e.py`：对运行中的后端走完整生命周期（用例→设备→环境凭据→项目→run→证据上传与自动解析→锁定→缺陷→回归→关闭→双模式报告→归档），32 项断言，可重复执行。
- 修复：环境参数明文密码守卫抛出 `ValueError` 未转换，接口返回 500；现映射为 `PlaintextSecretError` → 422（新增服务层与 API 测试）。
- 修复：报告 `mode`（formal/internal）未持久化，事后无法分辨报告版本；现写入 `report_snapshot["mode"]`。
- 改进：`EvidenceRead.parsed_metadata` 由 JSON 字符串改为对象返回（前端可直接消费），非法 JSON 容错为 null，附测试。
- 确认既有行为正确：证据上传须在结果锁定前完成；缺陷需 OPEN→IN_PROGRESS→RESOLVED 后才能登记回归；回归 PASS 自动写 `closed_at`；归档证据路径为 `evidence/` + `storage_path`。
