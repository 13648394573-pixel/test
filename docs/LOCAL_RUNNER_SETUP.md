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
