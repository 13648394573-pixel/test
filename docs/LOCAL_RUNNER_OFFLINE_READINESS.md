# 本地执行器：离线准备与现场验收清单

日期：2026-10-15，Asia/Shanghai。代码基线：`codex/skill-execution` / `ea2d91d6d8d1ef52567210d53e3560493859f23e`。

## 1. 当前结论

本次完成文档准备和本机只读检查，设备不可连接，现场各项均 **NOT_EXECUTED**。
不创建 Run/Session、不启动应用、不迁移数据库、不访问 ONU/OLT、不读取凭据值、不写现场配置。
不新增业务功能、依赖或数据库结构；不修改 main、Tag，不合并、推送或清理 worktree。

软件交付已有提交及离线验证；这不证明真实固件的所有输出、设备写入和中断恢复已通过。
现场记录继续追加到 LOCAL_RUNNER_LIVE_ACCEPTANCE.md，不覆盖旧结果。

## 2. 本机实查结果

| 检查 | 实际结果 | 影响与后续 |
|---|---|---|
| 分支和提交 | codex/skill-execution / ea2d91d；检查前干净 | 本轮只增加文档变更 |
| main | 0e915f2，干净 | 不从旧主线启动新生命周期验收 |
| Python / Node / npm | 3.12.5 / v24.16.0 / 11.13.0 | 版本满足 README 的基础要求 |
| Python 依赖声明一致性 | 4 项不符，见下表 | 测试通过不等于安装环境可复现；单独确认后再准备隔离环境 |
| 功能分支 .venv | 不存在 | 本次核对的是当前 python 环境，不冒称项目专属环境 |
| Chromium | Playwright 所指可执行文件存在 | 未启动浏览器，不能宣称登录、导航或截图成功 |
| OS 凭据后端 | Windows WinVaultKeyring | 未调用 get_password；账户是否仍有效未验证 |
| 主目录本机配置 | 存在，现有加载器校验通过，enabled=true，2 个目标、3 组访问绑定 | 仅结构检查，不输出地址、指纹或凭据引用内容 |
| 主目录 service_port_profiles | 0 个 | 不满足新 v2 会话双映射前置，须现场确认后补充；本轮不猜值 |
| 功能分支默认配置 | data/local-runner/config.json 不存在 | 不自动复制主目录配置，也不改变旧绑定 |
| 当前进程配置路径变量 | 未设置 | 不代表其他终端或服务的环境；不能据此宣称 Runner 已启用 |
| 测试网卡 | 以太网 4，Up | 仅本机链路状态，不能证明已接目标 ONU、DHCP、路由或 WAN 归属 |
| 数据/日志目录 | 功能分支 data 存在；data/runner-evidence、data/evidence、data/reports、logs 尚不存在 | 未创建目录或做写入探测；未验证 ACL/磁盘空间/存储写入能力 |
| Git 忽略规则 | 本机配置、证据/报告探针路径、日志、node_modules、dist 均被忽略 | 只查询规则，未创建这些探针文件 |

依赖以 backend/pyproject.toml 的实际约束逐项比较，不进行安装或升级：

| 包 | 当前 python 环境 | 项目声明 |
|---|---|---|
| fastapi | 0.115.6 | >=0.116,<1 |
| paramiko | 5.0.0 | >=3.5,<4 |
| pillow | 12.3.0 | >=11,<12 |
| uvicorn | 0.34.0 | >=0.35,<1 |

上述为准备差异，不直接认定为业务 Bug。建议另行确认后在隔离虚拟环境安装项目已声明的依赖并复验，不调整共享系统 Python，也不借此修改依赖范围。

## 3. 启动前清单（本轮不执行）

- [ ] 固定使用本功能分支的代码，记录实际启动解释器和依赖版本。
- [ ] 备份并确定独立验收数据库；使用已有迁移到当前 head，不使用生产历史库、不手改表、不以 create_all 代替迁移。本轮未检查数据库版本/数据，也未执行备份。
- [ ] 为新会话确认完整 IPOE/PPPOE 映射和目标引用；GEM/VLAN/Profile/候选 ID 不从文档样例直接抄用。复用已有映射时不要求创建候选 ID；没有候选 ID 不代表自动分配。
- [ ] 明确配置绝对路径、数据库 URL、Evidence/Runner Evidence/Report/日志根目录，避免相对路径落入另一个 worktree。检查空间和实际写入权限；本轮不写入探测。
- [ ] 新电脑需用户通过既有隐藏输入入口重新登记凭据；不把密码写入 JSON、文档、命令行或 Git。当前后端类型可用不等于六项凭据已登记。
- [ ] 后端只绑定 127.0.0.1:8000、单 worker；Runner 验收不使用 README 通用 --reload 模式。按 LOCAL_RUNNER_SETUP.md 设置 PYTHONPATH 和配置路径。
- [ ] 前端在该分支 frontend 目录启动，保持既有 Host/Origin 同源规则；不通过删除 Origin 或放开安全校验解决问题。
- [ ] 确认启动不会进行设备 I/O；恢复记录必须可见，但不得自动重试、认领端口或解锁历史结果。

## 4. 现场验收顺序与通过标准

所有步骤目前均 NOT_EXECUTED。先记录目标型号/版本、SN（报告脱敏）、FSP/ONT、Profile、SSH 指纹可信核对、测试网卡、配置与代码 hash。历史位置和端口只作线索，不作当前事实。

| 阶段 | 操作与通过标准 | 停止条件 |
|---|---|---|
| A 只读身份与映射 | 单独批准查询；确认当前 SN/FSP/ONT/Profile、完整 GEM/VLAN 映射及端口详情，保存脱敏原始输出/证据 | 身份不一致、指纹改变、未知/不完整输出则停止，不注册或下发 WAN |
| B 已有映射复用 | 通过实际平台链路识别 FOUND，账本 REUSED、消费者正确、不创建重复端口；核查证据 hash、快照与旧历史不变 | 不推进到注册/WAN 写入；若无法隔离只读步骤，停止整体 advance，不用历史授权代替审批 |
| C 缺失时创建 | 另行批准可恢复的专用测试资源；预览完整目标/映射/候选 ID/hash，执行前核对空闲及身份；单次创建后独立核验并记录 CREATED | 未确认候选、冲突、超时或身份漂移即人工恢复，不重试、不猜成功 |
| D 中断处理 | 只在另行批准的专用测试会话验证；重启后查看恢复状态，显式只读核对，未知资源不自动归属或删除 | 不为了制造故障直接中断在用设备；真实写入中断可能产生未知现场状态，未经专项批准不做 |
| E 安全清理 | 另行批准删除预览中的本会话已核验创建资源；END_POLICY 或人工恢复阶段，独立预览、确认、逐条缺失后验；REUSED/保留消费者不删除 | 部分失败立即停止；显示 UNCERTAIN/NOT_PROCESSED，重复请求不重复写入 |
| F 收尾与历史 | 核对脱敏证据、事件、hash、旧 Run/LOCKED/Snapshot/Report/Archive 不变，记录实际耗时和问题 | 动作 PASS 不等于测试 PASS；不自动 LOCK 或生成整体成功结论 |

清理后仍 MANUAL_REQUIRED，不代表 WAN 已恢复，也不自动继续测试。完整 WAN 自动恢复仍 HOLD；LAN 端口绑定/NAT 留给独立功能测试 Skill。
禁止凭离线测试数字给现场项目填 PASS。不得从整体 advance 意外跨入未获批准的 WAN/注册动作。

## 5. 单轮记录模板

- 日期/执行人、代码提交、配置 hash、依赖环境：待填写。
- DUT 型号/版本、SN 脱敏标识、OLT 型号、FSP/ONT、Profile、网卡：现场重新核实。
- 授权范围：只读 / 明确 CREATE / 明确 DELETE，附当前预览 hash；不互相替代。
- Run/Result/Session ID：本轮未创建，现场批准后填真实新记录，不改旧数据。
- 步骤 A–F：NOT_EXECUTED；逐项填真实结果及停止原因。
- Evidence ID/SHA256、账本事件、创建/复用来源、部分失败项：待执行后填写。
- 原配置/结束状态/保留责任/人工恢复项：待核对，不预填 VERIFIED。
- 测试准备、执行、证据整理耗时和阻塞问题：待计时。

## 6. 本轮出口

离线准备已记录；现场门禁仍待设备及运行条件就绪。下一步可单独处理隔离运行环境与非秘密配置准备，设备接入后从 A 开始。没有执行注册、WAN 下发、端口写入或新的真实测试任务。

## 7. 隔离环境实录（2026-10-15 追加）

第 2 节保留首次系统 Python 检查状态；本节为独立环境实际结果，不覆盖旧记录。

- 功能分支 .venv：Python 3.12.5，未启用 system-site-packages。执行 `.venv/Scripts/python.exe -m pip install -e "backend[dev]"` 成功；全部直接依赖及 dev 约束符合，`pip check` 返回 No broken requirements found。未修改系统 Python、依赖声明或业务代码。
- 关键版本：FastAPI 0.143.1、Paramiko 3.5.1、Pillow 11.3.0、Uvicorn 0.54.0、Playwright 1.64.0、SQLAlchemy 2.1.4、Alembic 1.20.0、Pydantic Settings 2.16.0、Pytest 8.4.2。
- 既有主目录配置未变，双业务映射仍待现场确认；未读取凭据值、创建正式会话或访问设备。

### 实际验证：未通过

使用隔离解释器运行 `python -m pytest backend/tests -q -p no:cacheprovider --basetemp=C:/Users/admin/AppData/Local/Temp/twb-task7-isolated-20261015 --tb=short`，设置 PYTHONDONTWRITEBYTECODE=1。退出码 1：**835 passed、1 failed、10 errors、2 warnings，470.33s**。仅使用临时测试数据和离线替身，无现场数据库迁移。本轮未重跑前端测试/构建。

1. **10 项错误：浏览器缺失。** Playwright 1.64.0 要求 chromium_headless_shell-1248，真实离线页面测试在 fixture 启动时找不到可执行文件，而非页面断言失败。执行 `python -m playwright install chromium` 后下载 197.5 MiB Chrome for Testing，进度缓慢，本轮主动停止下载，未声称安装完成；已核对没有该下载命令的残留进程。
2. **1 项失败：SSH 测试替身兼容。** `test_known_host_pin_checked_before_authentication_on_real_paramiko_flow[True]` 使用部分接口的 Transport 替身；Paramiko 3.5.1 的 SSHClient.connect 在认证前调用 set_gss_host，替身缺少此方法并抛 AttributeError。真实连接器的 Transport 并非此替身，不能据此认定真实设备认证失败。
3. **最小复现：** 原测试文件仅选择 known_host_pin_checked_before_authentication_on_real_paramiko_flow，结果 1 failed / 1 passed / 11 deselected（1.70s）；同一 AttributeError 可重现。没有修改替身、跳过断言或改生产安全逻辑；另一分支通过也不能单独证明新环境的全部指纹安全断言有效。
4. **警告：** 未安装 pytest-asyncio 时旧 asyncio_default_fixture_loop_scope 配置提示未知；新 Starlette TestClient 提示 httpx 弃用。本轮不增加插件或改客户端。

### 后续最小处理

单独确认后，仅补足已有 SSH 测试替身必要接口，保持正确指纹允许认证、错误指纹在认证前拒绝的断言；不得放宽指纹保护或使用声明外 Paramiko 5 取巧。网络适合时补齐当前版本浏览器，仅运行离线页面验证，再执行隔离环境全量回归；原环境 846 passed 不作为新环境通过证据。

当前：依赖安装合规，隔离运行验收 **HOLD**，现场 **NOT_EXECUTED**。保留被 Git 忽略的 .venv 和失败日志，不删除用户数据；本轮交付变更仍仅两份文档，未提交或推送。

## 8. 已批准的最小兼容性修复及复验（2026-10-15）

第 7 节保留失败时点；用户同意继续后，交付变更范围扩为原两份文档及 backend/tests/test_local_runner_review_gates.py，仅测试代码，没有生产修改。

- 先将错误指纹断言从任意 Exception 收紧为 HostKeyFingerprintMismatchError，隔离环境明确 RED：2 failed / 11 deselected（1.73s），均因替身缺少 set_gss_host。这样原来错误指纹分支不能再由无关 AttributeError 假通过。
- 仅给测试 Transport 增加 gss_kex_used=false 及 set_gss_host，并要求 gssapi_requested=false。真实 SSHClient 流程、认证策略及正确/错误指纹两分支仍执行；GREEN：2 passed / 11 deselected（1.13s）。没有放宽生产指纹核对或吞掉真实异常。
- 尝试 `playwright install --only-shell --no-remove chromium` 下载最小 118.1 MiB 组件，仍缓慢，主动停止；未删除旧浏览器或强制重装。两次停止下载不记作成功。
- 随后在依赖声明 >=1.55,<2 内为 .venv 选择 Playwright **1.61.0**（pyee 13.0.1），与本机已安装浏览器匹配，未修改依赖范围或系统 Python。它是本机运行环境选择，不是承诺任意未来最新版均兼容，也不是仓库级锁文件。
- 使用该隔离解释器，配套 Chromium 路径存在，headless 实际启动成功；page.set_content 渲染内存页面并断言正文成功，无真实设备请求。并非仅凭旧缓存存在就宣称修复。
- 定向运行 test_local_runner_review_gates.py、test_onu_web_adapter.py、test_verified_onu_adaptation.py：**36 passed，16.49s**；覆盖此前的浏览器 fixture 错误与 SSH 替身失败。
- 全部直接依赖/dev 版本约束重新核对通过，pip check 无冲突。第 7 节其他依赖版本不变；Pytest 配置及 Starlette 弃用警告尚未处理，本轮不扩展。

复现环境的安装命令（项目根目录；换电脑时还需安装同版本配套浏览器，不能复制 OS 凭据）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
.\.venv\Scripts\python.exe -m pip install "playwright==1.61.0"
.\.venv\Scripts\python.exe -m playwright install --only-shell --no-remove chromium
.\.venv\Scripts\python.exe -m pip check
```

以上用于复现本次版本选择，不替代全量回归，不表示已在新电脑执行。后续启动/测试使用 .venv/Scripts/python.exe，避免退回系统解释器。无头组件仅证明 headless 路径，未验证 headed 浏览器模式。

最终全量回归完成：隔离解释器运行 backend/tests，禁用测试缓存和 pyc，独立 basetemp 为 twb-isolated-final-20261015。实际 **846 passed、2 warnings，446.89s，exit 0**；此前的 1 failed / 10 errors 均未再出现，没有跳过相关用例。两条警告仍为第 7 节列出的测试配置和 Starlette/httpx 弃用提示，不伪称输出无警告。

隔离离线运行门禁 **PASS**，不是现场或完整恢复 PASS。现场仍 **NOT_EXECUTED**，缺少双业务映射及分支配置的前置不变。生产连接逻辑、依赖声明、系统 Python、main 和数据库未修改；当前一个测试文件和两份准备文档待审核，未提交/推送。下一步可审核并固化该最小修正和准备记录，设备可用后再另行授权只读验收。
