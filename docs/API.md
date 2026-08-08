# Test Workbench API

## 基础规则

- 默认地址：`http://127.0.0.1:8000`
- 前缀：`/api`
- 普通请求/返回：JSON
- 文件上传：`multipart/form-data`
- 文件下载：二进制响应
- 当前无认证、分页和多用户权限

业务错误返回`{"detail":"..."}`；Pydantic校验失败返回FastAPI标准`422`结构。

## 健康检查

| 方法 | 路径 | 成功 |
|---|---|---|
| GET | `/api/health` | `200`，`{"status":"ok","app":"Test Workbench"}` |

## Device Library

| 方法 | 路径 | 用途 |
|---|---|---|
| GET/POST | `/api/devices` | 列表/创建 |
| GET/PUT/DELETE | `/api/devices/{device_id}` | 详情/完整更新/删除 |

创建返回`201`；删除返回`204`。`serial_number`重复返回`409`，不存在返回`404`。

## Test Case Library

| 方法 | 路径 | 用途 |
|---|---|---|
| GET/POST | `/api/test-cases` | 列表/创建TestCase聚合 |
| GET/PUT/DELETE | `/api/test-cases/{test_case_id}` | 详情/整体更新/级联删除 |

请求包含`case_code`、`title`、`device_type`、`category`、`priority`、`preconditions`、`description`、`enabled`和非空`steps`。Service自动生成连续`step_number`。重复`case_code`返回`409`。

## Environment Profile

| 方法 | 路径 | 用途 |
|---|---|---|
| GET/POST | `/api/environment-profiles` | 列表/创建 |
| GET/PUT/DELETE | `/api/environment-profiles/{profile_id}` | 详情/整体更新参数/删除 |

Profile名称唯一，参数键在Profile内唯一。创建Run只能选择enabled Profile；历史Run Snapshot不受Profile更新或删除影响。

## Test Project与Run

| 方法 | 路径 | 用途 |
|---|---|---|
| GET/POST | `/api/test-projects` | 项目列表/创建 |
| GET/PUT/DELETE | `/api/test-projects/{project_id}` | 详情/更新/删除无历史项目 |
| GET/POST | `/api/test-projects/{project_id}/runs` | Run历史/创建Run |
| GET | `/api/test-runs/{run_id}` | Run详情、Result和环境快照 |
| PUT | `/api/test-runs/{run_id}/results/{result_id}` | 编辑DRAFT结果 |
| POST | `/api/test-runs/{run_id}/results/{result_id}/lock` | 锁定结果 |

创建Run请求：

```json
{
  "device_source_id": "UUID",
  "environment_profile_id": "UUID"
}
```

结果更新字段：`result`、`actual_result`、`blocked_reason`、`test_notes`。BLOCKED必须有原因；锁定前必须有有效结果。LOCKED修改返回`409`，全部结果LOCKED后Run自动COMPLETED。

## Evidence

| 方法 | 路径 | 用途 |
|---|---|---|
| GET/POST | `/api/run-results/{result_id}/evidences` | Result附件列表/上传 |
| GET/POST | `/api/defects/{defect_id}/evidences` | Defect附件列表/上传 |
| GET | `/api/evidences/{evidence_id}/download` | 下载并验证文件 |
| DELETE | `/api/evidences/{evidence_id}` | 按生命周期删除 |

上传字段：`category=SCREENSHOT|LOG|CONFIG|OTHER`、`description`、`file`。默认大小上限由`TEST_WORKBENCH_EVIDENCE_MAX_SIZE_MB`控制。

- RunResult：仅DRAFT允许上传/删除。
- Defect OPEN/IN_PROGRESS：允许上传和删除。
- RESOLVED：允许新增，不允许删除已有Evidence。
- CLOSED：完全只读。
- 文件缺失返回`410`，过大返回`413`，生命周期冲突返回`409`。

## Defect与Regression

| 方法 | 路径 | 用途 |
|---|---|---|
| GET/POST | `/api/defects` | 列表（支持status/severity过滤）/创建 |
| GET/PUT | `/api/defects/{defect_id}` | 详情/编辑 |
| PUT | `/api/defects/{defect_id}/status` | 状态流转 |
| GET/POST | `/api/defects/{defect_id}/regressions` | 回归历史/追加回归 |

Defect创建必须引用LOCKED FAIL/BLOCKED Result；一个Result最多创建一个Defect。无DELETE API。

状态：`OPEN`、`IN_PROGRESS`、`RESOLVED`、`REOPENED`、`CLOSED`。非法流转返回`409`。

Regression引用同用例的新LOCKED Result：PASS使RESOLVED→CLOSED；FAIL使RESOLVED→REOPENED；BLOCKED只追加记录。

## Report与Archive

| 方法 | 路径 | 用途 |
|---|---|---|
| GET/POST | `/api/test-runs/{run_id}/reports` | Run报告列表/生成 |
| GET | `/api/test-projects/{project_id}/reports` | 项目报告列表 |
| GET | `/api/reports/{report_id}` | 报告元数据和Snapshot |
| GET | `/api/reports/{report_id}/download` | 下载HTML |
| GET/POST | `/api/reports/{report_id}/archive` | 获取/创建唯一Archive |
| GET | `/api/archives/{archive_id}` | Archive元数据和manifest |
| GET | `/api/archives/{archive_id}/download` | 下载ZIP |

只有COMPLETED且全部结果LOCKED的Run可生成Report。Report生成后不可修改；Archive打包前校验HTML和Evidence SHA256。同一Report重复创建Archive返回`409`，文件篡改或状态不满足返回`409`。

## 通用状态码

| 状态 | 含义 |
|---:|---|
| 200 | 查询或更新成功 |
| 201 | 创建成功 |
| 204 | 删除成功，无响应体 |
| 404 | 资源不存在 |
| 409 | 唯一性、锁定、状态机、不可变或hash冲突 |
| 410 | Evidence元数据存在但文件缺失 |
| 413 | 上传文件超过限制 |
| 422 | 参数、来源Result或业务输入无效 |
