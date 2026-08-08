# Test Workbench V1 Release Final Approval

## 1. 发布候选基线

| 项目 | 记录 |
|---|---|
| 验证日期 | 2026-08-08 |
| 分支 | `main` |
| RC Commit | `dde3cf5b150456e4afb1075dee8b337d1af14b4c` |
| RC Tag | `v1.0.0-rc1` |
| 验证范围 | 重启恢复、重复Report/Archive、真实DUT复测、自动化回归与生产构建 |
| 范围约束 | 未修改业务代码、数据库设计或V1功能范围；未创建Sprint |

验证开始和结束时均确认`main`与`v1.0.0-rc1`指向同一RC Commit。运行验证只增加本地Git忽略的数据与报告；RC Tag内容未改变。

## 2. 重启恢复验证

使用`data/v1_beta_round1.db`及固定的Evidence/Report存储根，连续启动两个相互独立的FastAPI进程，并在每次启动后重新读取同一历史Run、HTML Report和ZIP Archive。

| 检查项 | 结果 |
|---|---|
| 两次健康检查 | `status=ok` / `status=ok` |
| 历史Run | `b179fb82-f1bc-488a-ab2a-5bcdfc62b309`，两次均为`COMPLETED` |
| 原Report | `RPT-000003`，SHA256 `928801f56bce0ad776a35171d7b566b7bb33f20941e015b6d574df4762842d1e` |
| 原Archive | `ARC-000003`，SHA256 `6ecb924f2bb69629fce8accda4191b8f1c8623a5193de6ab20d55be397ab4c7e` |
| 重启前后文件哈希 | 完全一致 |
| 结论 | **PASS** |

## 3. 重复Report / Archive验证

对上述已完成且12项结果全部LOCKED的历史Run再次生成报告，不修改原Run、Snapshot、Result、Evidence、Report或Archive。

| 检查项 | 结果 |
|---|---|
| 新Report | `RPT-000004`，Run内版本`2` |
| HTML SHA256 | `3265003e10df95599c621d3b40c58e8ca4184d42153bb7f3cc311298f199fba9` |
| 新Archive | `ARC-000004` |
| ZIP SHA256 | `140aca74a9fe64590c4c99358f15d9f268a99474689c144a4e0c38f3bece195c` |
| 下载文件与元数据哈希 | 一致 |
| 对同一Report再次创建Archive | HTTP `409` |
| 结论 | **PASS** |

验证后SQLite `quick_check=ok`、`foreign_key_check=0`。业务计数为4个Run、12个RunResult、16个Evidence、4个Report和4个Archive；12个RunResult仍全部LOCKED。

## 4. 真实DUT最终复测记录

### 4.1 DUT与环境

| 项目 | 记录 |
|---|---|
| DUT | XPON ONU `UN-769XR`；SN/MAC仅保存在受控本地记录中 |
| OLT | Huawei MA5800-X7 |
| 接入位置 | F/S/P `0/2/10`，ONT ID `48` |
| Profile | Line/Service Profile `10/10` |
| 业务配置 | VLAN `1000`，IPoE + PPPoE |
| 操作范围 | 仅查询现有状态和读取ONU Web；未重新注册、未下发配置 |

### 4.2 验证结果

| 验证项 | 实际结果 | 判定 |
|---|---|---|
| ONU online | OLT `Run state=online` | PASS |
| Profile匹配 | OLT `Match state=match` | PASS |
| PON状态 | ONU Web `ONU State=O5` | PASS |
| IPoE | VLAN 1000，地址与网关已脱敏，状态`up` | PASS |
| PPPoE | VLAN 1000，地址与网关已脱敏，状态`up` | PASS |
| 网络连通 | `www.baidu.com`，4发4收，0%丢包，平均RTT `14.407 ms` | PASS |

### 4.3 Evidence

本轮证据位于受控本地目录：

`C:\Users\admin\onu_test\screenshots\20260808_120300\`

关键证据包括ONU Web登录、设备信息、WAN、PON、Ping截图与文本，以及OLT ONT/WAN只读查询文本和渲染图片。产测报告哈希：

- JSON：`27c7491c9c968fd79fc0ffa64f9aae01c32fa2b56bd2a355a42a23d1b82fad36`
- HTML：`8ccf663baf07aa83d35a3026f03c7f4196320323e2134bba6fdc27d6bababbeb`
- DOCX：`ad3a94fe4ab569a6efb7281d414f2d24a88797aa453ed9f62328477b74fd9225`

## 5. 自动化回归与构建

| 验证项 | 命令 | 结果 |
|---|---|---|
| 后端 | `python -m pytest backend/tests -q`（使用短系统临时根） | 117 passed |
| 前端 | `npm.cmd test -- --reporter=dot --maxWorkers=1` | 39 passed |
| 生产构建 | `npm.cmd run build` | PASS，46 modules transformed |

Windows长pytest临时路径可能触发传统`MAX_PATH`限制。本次改用短系统临时根后117项全部通过；该现象属于测试运行环境限制，不是产品业务断言失败。

## 6. 已接受观察项

| 观察项 | 等级 | 处理与发布影响 |
|---|---|---|
| OLT显示`Config state=failed`，但`Run state=online`、`Match state=match`且O5/IPoE/PPPoE/网络连通全部通过 | P2 / Accepted Observation | 不阻断V1.0.0；后续设备兼容性验证继续跟踪 |
| SN认证场景下ONU Web显示`LOID Error`；本轮未使用LOID认证 | P2 / Accepted Observation | 不影响当前SN认证场景；不扩展RC范围 |

本轮未发现新的P0或P1问题，未发现数据漂移、历史记录修改、文件哈希异常或重启恢复失败。

## 7. 最终批准结论

V1.0.0-rc1在既定V1范围内完成了真实ONU/OLT闭环、重启恢复、重复报告归档、数据完整性、自动化回归和生产构建验证。全部发布阻断门禁通过，已知观察项均有明确边界且不影响当前核心场景。

**Final Validation：PASS**

**Release Decision：APPROVED FOR V1.0.0 STABLE RELEASE PREPARATION**

正式发布前仅允许：

1. 提交本批准文档并确认`main`工作区干净。
2. 复核提交内容仅包含本文件。
3. 经发布人明确批准后，在该文档提交后的`main`创建注释Tag `v1.0.0`并推送。

本阶段未创建`v1.0.0` Tag。
