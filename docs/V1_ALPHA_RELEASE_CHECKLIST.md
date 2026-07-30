# Test Workbench V1 Alpha Release Checklist

## 发布基线

- 分支：`main`
- Feature Complete Commit：`edc26db330f57e01e192acd7f2c7260fecf9c747`
- 产品定位：面向个人网络设备测试工程师的本地测试记录闭环管理平台
- 适用范围：ONU、OLT、光猫等设备的手工测试过程管理

## 1. Sprint 0–7 完成情况

| Sprint | 主题 | 状态 | 已交付能力 |
|---|---|---|---|
| 0 | Foundation | 已完成 | React、FastAPI、SQLite、ORM、Alembic、配置、日志和测试基础 |
| 1 | Device Library | 已完成 | 设备档案新增、查询、编辑和删除 |
| 2 | Test Case Library | 已完成 | 测试用例、步骤、优先级、启停和模板化维护 |
| 3 | Test Execution | 已完成 | 测试项目、设备与用例选择、手工执行、结果和历史快照 |
| 4 | Defect & Regression | 已完成 | 缺陷生命周期、失败证据关联、追加式回归和状态联动 |
| 5 | Test Evidence & Result Integrity | 已完成 | 实际结果、阻塞原因、备注、结果锁定和附件管理 |
| 6 | Environment Snapshot | 已完成 | 环境模板、参数管理、Run环境快照和历史展示 |
| 7 | Report & Archive | 已完成 | 报告快照、HTML导出、SHA256校验和ZIP归档 |

## 2. 当前系统能力

- 管理ONU、OLT、光猫等DUT设备档案。
- 管理带步骤的测试用例，并按设备类型、分类和优先级组织。
- 创建测试项目，选择设备、环境和测试用例后执行手工测试。
- 保存PASS、FAIL、BLOCKED结果，以及实际结果、阻塞原因和测试备注。
- 锁定完成结果，保持设备、用例和环境历史快照不可漂移。
- 为测试结果或缺陷上传、下载和删除本地Evidence，并校验文件SHA256。
- 从锁定的FAIL/BLOCKED结果创建缺陷，记录独立缺陷生命周期和追加式回归。
- 汇总项目、运行、结果、证据、缺陷和回归数据，生成不可变HTML报告。
- 创建单一ZIP归档，归档前校验报告和Evidence完整性。

## 3. 已知技术债

- `README.md`、`ARCHITECTURE.md`、`DATABASE.md`、`API.md`仍主要描述早期模块，需要在Beta发布前按Sprint 0–7真实实现统一更新。
- SQLite与本地文件适合单机使用，但数据库、Evidence、报告目录尚无自动备份和恢复工具。
- 文件完整性可通过SHA256发现异常，但文件丢失或损坏后仍需人工恢复。
- HTML报告采用固定基础模板，超长字段、大表格和跨浏览器打印效果仍需Beta验证。
- Windows环境运行Vitest需要使用`--maxWorkers=1`以避免worker内存不足。
- 当前自动测试以单元和API集成为主，尚需真实ONU/OLT/光猫场景的Beta验收数据。

## 4. Beta验证计划

1. **场景覆盖**：至少使用ONU、OLT、光猫各一种设备，完成设备建档、用例选择、环境快照、执行、缺陷、回归、报告和归档闭环。
2. **结果完整性**：验证DRAFT可编辑、LOCKED不可修改，且Defect/Regression只能引用符合规则的锁定结果。
3. **历史稳定性**：修改设备、用例和环境模板后，确认历史Run与已生成Report内容不变化。
4. **Evidence验证**：覆盖截图、日志、配置文件和其他类型，验证上传、下载、生命周期限制、缺失文件和hash异常提示。
5. **报告归档**：验证仅COMPLETED且全部LOCKED的Run可生成报告；重复归档返回409；ZIP内容与manifest一致。
6. **数据规模**：使用不少于100条用例和多个大附件执行一次完整流程，观察列表响应、报告生成时间和磁盘占用。
7. **升级验证**：从空数据库执行全部迁移，并使用一份Sprint 6基线数据升级到最新版本。
8. **退出标准**：无数据损坏或阻断主流程的问题；已知问题有记录和可接受的规避方式。

## 5. 发布前检查项

### 自动化基线

- [x] main指向Feature Complete提交`edc26db330f57e01e192acd7f2c7260fecf9c747`
- [x] 后端全量测试：117 passed
- [x] 前端全量测试：39 passed
- [x] 前端生产构建通过
- [x] Feature Complete合并后main工作区已确认干净
- [x] Sprint功能分支和worktree已清理

### 发布操作

- [ ] 从空数据库执行`alembic upgrade head`
- [ ] 备份现有SQLite数据库、Evidence、Report和Archive目录
- [ ] 检查`.env`配置、存储路径、磁盘空间和目录读写权限
- [ ] 启动前后端并完成健康检查
- [ ] 完成一条真实设备测试闭环冒烟验证
- [ ] 验证HTML下载、SHA256校验和ZIP解压内容
- [ ] 审核已知技术债与Beta问题记录
- [ ] 更新早期架构、数据库、API和README文档
- [ ] 验收通过后创建V1 Alpha发布提交和版本标签
