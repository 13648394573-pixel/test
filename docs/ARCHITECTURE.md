# Test Workbench 架构

## 产品边界

Test Workbench 是单用户、本地运行的网络设备手工测试记录平台。核心目标是统一设备、用例、环境、执行、证据、缺陷、回归、报告和归档数据，使测试历史可追溯。

不包含AI、多用户权限、企业协作、云存储、自动发现设备或自动化脚本执行。

## 系统结构

```text
React + TypeScript + Vite
          │ /api
          ▼
FastAPI Router
    ↓ Schema
    ↓ Service
    ↓ Repository
    ↓ SQLAlchemy Model
          │
          ├── SQLite：业务数据、JSON Snapshot、文件元数据
          └── 本地文件：Evidence、HTML Report、ZIP Archive
```

前端开发端口为`5173`，通过Vite代理访问本地FastAPI `8000`。后端在lifespan中初始化日志、SQLite Engine和Session factory，并在关闭时释放Engine。

## 后端模块

| 模块 | 责任 |
|---|---|
| `devices` | DUT档案与序列号唯一性 |
| `test_cases` | TestCase聚合及CaseStep整体替换 |
| `test_execution` | TestProject、TestRun、RunResult和历史快照 |
| `environments` | EnvironmentProfile、参数和Run环境快照 |
| `evidence` | 文件流式存储、元数据、SHA256和生命周期规则 |
| `defects` | Defect状态机及追加式Regression |
| `reports` | Report Snapshot、HTML渲染、Archive manifest和ZIP |

所有业务模块保持：

```text
Router → Schema → Service → Repository → Model
```

- Router：HTTP路径、依赖、状态码。
- Schema：Pydantic输入校验与输出序列化。
- Service：事务边界、状态机、不变性和跨仓储规则。
- Repository：SQLAlchemy查询与持久化。
- Model：表、关系、约束和ORM级不可变保护。

## 前端结构

`App.tsx`提供单页导航，各领域目录包含页面、组件、类型、API client和测试：

```text
devices/  testCases/  testExecution/  defects/  environments/  reports/
```

前端只调用现有REST API，不直接接触SQLite或文件路径。

## 核心数据流

创建执行记录：

```text
选择Project + Device + enabled EnvironmentProfile
→ POST Run
→ 同事务创建TestRun、RunResult和Environment Snapshot
→ 冻结Device/Case/Environment数据，snapshot_version=1
```

结果与证据：

```text
DRAFT Result编辑
→ Evidence上传并计算SHA256
→ Result LOCKED
→ Result、执行字段和Snapshot不可再修改
→ 全部LOCKED后Run变为COMPLETED
```

缺陷回归：

```text
LOCKED FAIL/BLOCKED Result
→ Defect（一个Result最多一个Defect）
→ 追加Regression引用新的LOCKED Result
→ PASS关闭 / FAIL重开 / BLOCKED仅记录
```

报告归档：

```text
COMPLETED且全部LOCKED Run
→ Report Snapshot + HTML + SHA256
→ 单一Archive + manifest + 已校验Evidence + ZIP + SHA256
```

## 历史完整性

- Device、Case和Environment源数据可继续维护，但历史Run使用JSON Snapshot。
- Snapshot版本固定为1，ORM拒绝修改已创建Snapshot。
- LOCKED RunResult不可编辑或解锁。
- Regression追加式，不可修改或删除。
- Evidence元数据不可修改；文件生命周期由Result/Defect状态控制。
- Report和Archive生成后不可修改或删除；每个Report最多一个Archive。
- SQLite连接启用`PRAGMA foreign_keys=ON`。

## 存储与恢复

SQLite只保存文件元数据和相对路径；Evidence、HTML和ZIP保存在配置的本地目录。备份必须同时包含数据库、Evidence根和Report根。

历史Beta数据曾使用不同存储根命名空间，恢复时需要按数据库记录的`storage_path`和SHA256合并到统一根。详情见[V1备份恢复演练](V1_BACKUP_RESTORE_DRILL.md)。
