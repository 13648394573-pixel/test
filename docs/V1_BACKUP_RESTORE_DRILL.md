# V1 Backup / Restore Drill

## 演练信息

| 项目 | 记录 |
|---|---|
| 日期 | 2026-08-08 |
| 分支/基线 | `main` / `5e362687a3a89ee5b4336c9a1db68105858ea875` |
| 范围 | SQLite、Evidence、HTML Report、ZIP Archive |
| 运行目录 | `data/release-prep-20260808-rc1/`（Git忽略，不提交） |
| 目标 | 验证本地数据可完整备份、恢复、校验并由现有API读取 |

## 备份范围

- 数据库：`data/test_workbench.db`、`data/v1_beta_round1.db`
- Evidence：`data/evidence/`
- Report/Archive：`data/reports/`
- Manifest：`data/release-prep-20260808-rc1/sha256-manifest.csv`

未备份`node_modules`、`dist`、日志、缓存或源码工作区。

## 执行结果

| 检查项 | 结果 |
|---|---|
| 源文件数量 | 24 |
| 源文件总大小 | 2,405,331 bytes |
| 源→备份→恢复SHA256 | 24/24一致，PASS |
| 两个恢复数据库`PRAGMA quick_check` | `ok`，PASS |
| 两个恢复数据库`foreign_key_check` | 0条违规，PASS |
| Beta业务计数 | Device 2、Case 3、Project 1、Run 4、Result 12、Evidence 16、Defect 1、Regression 3、Environment 2、Report 3、Archive 3 |
| Result完整性 | 12个Result全部LOCKED |
| 统一恢复根后文件hash | Evidence 16/16、Report 3/3、Archive 3/3，PASS |
| 恢复API健康检查 | `status=ok` |
| 恢复API下载与hash | 22/22通过 |

## 恢复步骤

1. 将数据库、Evidence目录和Report目录恢复到独立位置，不覆盖现有运行数据。
2. 比对源、备份和恢复文件的SHA256清单。
3. 对SQLite执行`PRAGMA quick_check`和`PRAGMA foreign_key_check`。
4. 核对业务表计数及历史LOCKED结果。
5. 根据数据库`storage_path`把历史命名空间和当前命名空间文件合并到统一Evidence/Report根。
6. 使用恢复数据库和统一文件根启动FastAPI测试实例。
7. 经现有下载API读取16个Evidence、3份Report和3份Archive，并与数据库SHA256比较。

## 发现与技术债

历史Beta运行曾使用：

- `data/evidence/v1-beta-round1/`
- `data/reports/v1-beta-round1/`

当前恢复运行使用：

- `data/evidence/`
- `data/reports/`

数据库只保存相对`storage_path`，未保存文件根版本，因此直接配置单一根目录不能解析跨时期文件。本次通过hash驱动的人工合并恢复成功，没有修改数据库或历史记录。

RC1处理：

- 将该限制列为已知技术债。
- 正式部署必须固定Evidence和Report根，禁止在同一数据库生命周期中变更根目录。
- 正式备份需复制到工作区之外的独立介质；本演练目录仅用于验证。

## 结论

备份内容完整，恢复数据库、文件hash和下载API全部验证通过。本项目具备**人工备份/恢复能力**，但尚无自动备份工具，且历史存储根变更需要人工归一化。演练结论：`PASS with documented manual step`。
