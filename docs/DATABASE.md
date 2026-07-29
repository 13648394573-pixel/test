# Test Workbench 数据库

## 数据库引擎

当前使用本地 SQLite，默认连接地址：

```text
sqlite:///./data/test_workbench.db
```

可通过环境变量 `TEST_WORKBENCH_DATABASE_URL` 覆盖。应用和 Alembic 在首次连接前会创建 SQLite 文件的父目录。

## 当前数据表

### `devices`

| 字段 | SQLite/ORM 类型 | 必填 | 规则 |
|---|---|---:|---|
| `id` | `VARCHAR(36)` | 是 | UUID 字符串，主键 |
| `device_type` | `VARCHAR(50)` | 是 | 设备类型 |
| `vendor` | `VARCHAR(100)` | 是 | 厂商 |
| `model` | `VARCHAR(100)` | 是 | 型号 |
| `serial_number` | `VARCHAR(100)` | 是 | 唯一约束及唯一索引 |
| `mac_address` | `VARCHAR(17)` | 否 | MAC 地址 |
| `hardware_version` | `VARCHAR(100)` | 否 | 硬件版本 |
| `software_version` | `VARCHAR(100)` | 否 | 软件版本 |
| `created_at` | `DATETIME` | 是 | 默认 `CURRENT_TIMESTAMP` |
| `updated_at` | `DATETIME` | 是 | 默认 `CURRENT_TIMESTAMP`；ORM 更新时刷新 |

当前删除为物理删除，没有软删除字段。

## ORM 与 Session

- ORM Base：`backend/app/db/base.py`
- Device Model：`backend/app/models/device.py`
- Engine/Session factory：`backend/app/db/session.py`
- 请求级 Session：`backend/app/db/dependencies.py`

Session 配置为 `autoflush=False`、`expire_on_commit=False`。Repository 在新增、编辑和删除后提交事务。

## 数据库迁移

迁移工具为 Alembic，配置文件为 `backend/alembic.ini`。

当前迁移：

| Revision | 内容 |
|---|---|
| `20260729_0001` | 创建 `devices` 表及序列号唯一索引 |

在项目根目录执行升级：

```powershell
python -m alembic -c backend\alembic.ini upgrade head
```

回退一个版本：

```powershell
python -m alembic -c backend\alembic.ini downgrade -1
```

应用启动时仍会调用 `Base.metadata.create_all()`，用于确保已注册模型的表存在；正式结构变更应通过 Alembic 迁移记录。
