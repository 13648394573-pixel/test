# Test Workbench 架构

## 当前范围

Test Workbench 是本地运行的个人网络设备测试工作台。当前已完成基础工程和 Device Library（设备库），尚未包含测试项目、环境、用例或自动化执行模块。

## 前后端结构

```text
frontend/
  src/App.tsx                 应用入口与页面壳
  src/devices/                设备库页面、表单、类型和 API client

backend/
  app/main.py                 FastAPI 创建、生命周期、路由和异常映射
  app/core/                   配置与日志
  app/db/                     数据库引擎、Session、ORM Base 和请求依赖
  app/models/                 SQLAlchemy 数据模型
  app/devices/                Device Schema、Repository、Service 和 Router
  migrations/                 Alembic 迁移
```

前端使用 React、TypeScript 和 Vite，默认开发端口为 `5173`。Vite 将 `/api` 请求代理到本地 FastAPI `127.0.0.1:8000`。

后端使用 FastAPI、SQLAlchemy 和 SQLite。应用启动时加载配置、初始化日志、创建数据库引擎与 Session factory，并通过 FastAPI lifespan 管理引擎生命周期。

## 分层设计

Device Library 后端采用以下单向依赖：

1. **Router**：声明 HTTP 路径、状态码和请求依赖。
2. **Schema**：使用 Pydantic 校验输入并序列化输出。
3. **Service**：处理设备不存在、序列号重复等业务规则。
4. **Repository**：封装 SQLAlchemy 查询与事务提交。
5. **Model/Database**：定义 `devices` 表并保存数据。

前端采用以下结构：

1. `App` 挂载 `DeviceLibraryPage`。
2. `DeviceLibraryPage` 管理列表、表单开关、错误和 CRUD 状态。
3. `DeviceForm` 负责设备字段输入。
4. `deviceApi` 通过 `fetch` 调用 `/api/devices`。

## 数据流

读取流程：

```text
DeviceLibraryPage
→ deviceApi.list()
→ GET /api/devices
→ DeviceService.list()
→ DeviceRepository.list()
→ SQLite
→ DeviceRead JSON
→ 前端设备表格
```

写入流程：

```text
设备表单
→ DeviceInput
→ POST/PUT/DELETE API
→ Pydantic 校验
→ DeviceService 业务检查
→ DeviceRepository 提交事务
→ SQLite
→ 前端更新列表
```

后端将 `DeviceNotFoundError` 映射为 `404`，将 `DuplicateSerialNumberError` 映射为 `409`。
