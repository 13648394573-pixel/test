# Test Workbench API

## 基础规则

- 默认地址：`http://127.0.0.1:8000`
- API 前缀：`/api`
- 请求与返回格式：JSON
- 无认证、分页和多用户权限

健康检查：

```http
GET /api/health
```

成功返回：

```json
{
  "status": "ok",
  "app": "Test Workbench"
}
```

## Device 请求字段

`POST` 和 `PUT` 使用相同的完整请求结构：

```json
{
  "device_type": "ONU",
  "vendor": "Huawei",
  "model": "HN8546X6",
  "serial_number": "ONU-001",
  "mac_address": "00:11:22:33:44:55",
  "hardware_version": "V1",
  "software_version": "V5R020"
}
```

必填字段：`device_type`、`vendor`、`model`、`serial_number`。其余字段可为 `null`。字符串会去除首尾空格，长度限制与数据库字段一致。

设备返回结构在请求字段之外增加：

```json
{
  "id": "UUID",
  "created_at": "2026-07-29T08:00:00",
  "updated_at": "2026-07-29T08:00:00"
}
```

## Device API

### 获取设备列表

```http
GET /api/devices
```

- 成功：`200`
- 返回：设备数组，按创建时间倒序
- 无数据：`[]`

### 新建设备

```http
POST /api/devices
Content-Type: application/json
```

- 成功：`201`，返回完整设备
- 序列号重复：`409`
- 请求校验失败：`422`

### 获取设备详情

```http
GET /api/devices/{device_id}
```

- 成功：`200`
- 设备不存在：`404`

### 编辑设备

```http
PUT /api/devices/{device_id}
Content-Type: application/json
```

- 请求体：完整 Device 请求字段
- 成功：`200`，返回更新后的设备
- 设备不存在：`404`
- 序列号与其他设备重复：`409`
- 请求校验失败：`422`

### 删除设备

```http
DELETE /api/devices/{device_id}
```

- 成功：`204`，无响应体
- 设备不存在：`404`

## 错误返回

业务错误统一使用 FastAPI `detail` 字段：

```json
{
  "detail": "Device not found"
}
```

当前业务错误：

| HTTP 状态 | `detail` |
|---:|---|
| `404` | `Device not found` |
| `409` | `Serial number already exists` |

`422` 使用 FastAPI/Pydantic 的标准校验错误结构。
