# Local Runner 本机绑定

默认不启用；示例 `backend/config/local-runner.example.json` 不含设备地址、凭据或现场配置。
真实配置保存至已忽略的 `data/local-runner/config.json`，用
`TEST_WORKBENCH_LOCAL_RUNNER_CONFIG_PATH` 指定路径。仅用于本机开发环境、单进程、回环地址。
加载配置不连接设备。修改后必须重启；新配置不改变已有执行会话绑定。

## 配置与凭据

配置 schema_version=1。targets 按逻辑引用配置 MA5800（私网 host、port、预先人工核验的
SHA256 SSH 公钥指纹）和 ONU_WEB（私网 http/https url、neutral-v1、明确的 pc_interface_name）。
access_bindings 配置 OLT、ONU_WEB、PPPOE 三类访问对，分别指定不同的 username_ref/password_ref。
禁止把账号密码写入 JSON、URL、命令参数或提交到仓库。

在 backend 可导入的 Python 环境、本机交互终端中执行：

```powershell
python -m app.local_runner.setup --config data/local-runner/config.json --access-ref lab.olt.access
```

账号和密码均隐藏输入，只写入现有 OS keyring。每个逻辑引用分别登记。
写入失败会尝试恢复旧凭据对；若 OS 存储持续故障，则需要人工核对并重新登记，不能保证 OS
提供跨两次写入的原子事务。迁移电脑时只迁移非秘密配置；新电脑必须重新登记凭据。

## 验收边界

现场设备验收：NOT_EXECUTED。自动化步骤成功不等于产品测试 PASS；网络归属、恢复状态、
历史快照与锁定结果规则必须单独验证。此阶段不包含前端接入，不自动解锁或 LOCK 结果。

## 启动与执行

在项目根目录、已有后端依赖环境中设置（不需要新依赖或数据库迁移）：

~~~powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'backend')
$env:TEST_WORKBENCH_LOCAL_RUNNER_CONFIG_PATH = (Join-Path (Get-Location) 'data/local-runner/config.json')
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
~~~

不要使用多 worker、公开网卡绑定或热更新执行配置。配置非法会以安全错误码拒绝启动；
enabled=false 或没有指定配置路径时不启用 Runner。加载/重启不会登录设备或重放配置动作。
关闭前应完成或明确停止当前执行；中断的 RUNNING/RESTORING 会进入人工恢复。

Environment 的 olt_target_ref/onu_web_target_ref 必须匹配 targets 键；
olt_access_ref/onu_web_access_ref/pppoe_access_ref 必须匹配三种 access_bindings 键。
当前配置后重新创建会话；不要给旧 Run 补绑定。旧会话可以读取/下载，推进返回
409 RUNTIME_BINDING_REQUIRED。账号密码可以轮换，但不能将旧会话的 leaf refs 改指另一组条目。

通过已有 /api/skill-executions 创建、逐步 advance、respond；每次只推进一个持久化动作。
配置变更必须逐项明确 approved=true 并提交本次 preview_hash；respond 本身不会下发配置，
批准后仍需下一次 advance。网卡缺失/多地址/未知前缀时会等待接线，提示不等同于配置修改授权。
修正接线后使用最新交互 hash；旧确认不能代替新确认。

执行完成仍保持 DRAFT。核查结果、事实与证据后，用户通过已有结果 lock 接口明确锁定；
之后再使用原 Report/Archive 流程。不得将动作 PASS 当作整个测试 PASS。

## 网卡、指纹及换电脑

确认实际测试网卡名称；DHCP 地址每次从该网卡实时选择，只接受 ONU 所在真实子网的唯一有效地址。
不猜 /24、不自动选择其他网卡、不改系统路由。配置中网卡名称变更只影响重启后新建的会话。
OLT 指纹需在受信任现场人工复核；指纹改变时停机核对，不自动接受或更新 known_hosts。
迁移电脑后重新登记六个值，OS 凭据不随 Git、数据库、证据或 ZIP 迁移。

## 恢复边界

当前已有适配器只能证明部分注册信息，不能证明完整 WAN/service-port 恢复。
RESTORE 及恢复核验安全 BLOCKED，结果进入 MANUAL_REQUIRED，不把注册字段相等当作恢复完成。
应在现场人工核对原配置快照、WAN 与 service-port；保留中断与恢复记录，不手改数据库、
不伪造 VERIFIED、不重复执行未确认的变更。当前接口没有新增人工恢复关闭能力。
KEEP 仅在用户明确承担保留现场变更责任时选择，表示免除恢复，并非已经恢复。

已注册 ONU 没有真实 autofind 记录时，不生成虚构匹配事实；
在现有固定标准下，该项可能 FAIL。当前 PC Probe 只能证明绑定源地址的诊断成功，
不能独立证明实际下一跳经过目标 ONU、以及当前隔离链路属于指定 WAN。
因此即使仅一个 WAN 在线，也不生成 ipoe/pppoe.internet.pass；没有其他确定失败项时，
最终标准结果为缺少来源的 BLOCKED。等待接线前的历史 WAN/Ping 也不能作为当前归属证明。
保留 PC 指标和证据，继续其他收集，不把诊断动作 PASS 当作 WAN 测试 PASS。
系统默认 DNS 成功不能代替归属证明。现场联调结果必须与离线替身测试分开记录。

批准配置变更后，执行前仍重新只读核对 SN/FSP/ONT-ID；注册须确认目标未注册、
当前目标 ID 空闲且 autofind 身份匹配。身份改变、ID 被占用、service-port 归属不明或
未识别的读输出均安全阻塞。不能识别的固件输出须先提供脱敏样本审核，不猜测空结果。
固定 SSH 指纹在同一连接认证前校验，系统 known_hosts 不能绕过此校验。
Web 凭据及 PPPoE 凭据仅在动作内读取供脱敏；页面控件、普通文本与子帧在 PNG 前脱敏，
无法完成遮挡或存在不可核验 canvas 时不保存该截图。
