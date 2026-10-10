# ONU 本地适配器现场验证

日期：2026-10-10。修复前基线：7107c8e；本记录随本轮适配修复提交。

## 已固化能力

- MA5800 WAN 解析兼容现场的 `Index`、`IPv4 Connection status`、`Manage VLAN`、`Default gateway` 字段。
- ONU WAN 优先读取 `Status / Network Side` 下的 `status_wan.asp` 状态页，以协议区分 IPoE 与 PPPoE，不混用 IPv6 状态。
- Ping 收集诊断子框架结果，等待本次请求完成；已有结果必须经框架导航或被观察到清空，不能仅凭运行提示变化认为结果已更新。保留发包、收包、丢包及延迟。
- 配置命令支持显式 IP Host 索引，审批摘要绑定索引与 VLAN；拒绝两个协议使用相同索引。
- 文本及截图中的 SN、MAC 脱敏，文本输出同时覆盖缓存的 Ping 结果；现场网卡探测使用实际接口索引及绑定地址。

## 当前设备用法

本次 BT-G713AX-S / V3.1.0-261009 实测保留 IPoE Host 0，并使用独立 PPPoE Host 1。因此本设备应明确传入 `ipoe_ip_index=0`、`pppoe_ip_index=1`。

兼容旧调用的默认值仍为 IPoE 1、PPPoE 0，不能直接用于所有设备。执行配置前必须核对已有 Host 占用及审批内容；程序尚不自动选择空闲索引。现场 OLT 展示序号与配置索引不同，不应把显示值直接作为命令索引。

## 现场结果与证据

固化后的适配器直接执行，未再次下发配置：

| 检查 | 结果 |
|---|---|
| IPoE 状态 | up，nas0_0，VLAN 1000 |
| IPoE 域名 Ping | 4 发 4 收，丢包 0%，平均 10.910 ms |
| PPPoE 状态 | up，ppp0_nas0_1，VLAN 1000 |
| PPPoE 域名 Ping | 4 发 4 收，丢包 0%，平均 9.632 ms |

本地证据目录：`data/runner-evidence/adapter-validation/09fe7772-b3e7-49d7-9e6a-487d11b3fc73`，属于运行数据，不提交 Git。

此前现场另已确认 O5、双 WAN 及 PPPoE 网关/公网/域名连通。光功率只记录实测值，未作阈值合格判定；IPv6 未通过；电脑默认路由未绑定目标 ONU，不能据此宣称 LAN 上网通过。

## 验证方式

浏览器测试需要已安装 Playwright Chromium headless shell；缺失时执行 `python -m playwright install --only-shell chromium`。

后端使用短临时路径，避免 Windows 长路径导致文件创建失败。每次选择新的路径：

```powershell
python -m pytest backend/tests -q -p no:cacheprovider --basetemp=data/v-1010f
cd frontend
npm.cmd test -- --reporter=dot --maxWorkers=1
npm.cmd run build
```

## 边界

如果固件在同一框架中瞬间替换旧统计，且没有可观察的清空或导航，本适配器会安全超时，不把无法证明属于本次请求的统计判为 PASS。回归测试覆盖旧成功/旧错误统计保留、同结果导航刷新、清空后重现及缓存文本脱敏。

本轮最终全量验证：后端 359 passed（203.28 秒）；前端 54 passed；生产构建通过。初次后端验证出现 8 个 Windows 临时路径过长错误，缩短测试临时目录后全量通过，未为此修改业务逻辑。审核发现的 Ping 新鲜度与缓存脱敏问题已按测试先行修复，并通过独立复核；最终修复使用离线浏览器回归验证，未再次操作 DUT。

本次固化不修改数据库、不创建正式 TestRun、不自动锁定结果、不增加测试范围。WAN/Ping 适配器现场通过不等于完整 Skill 编排已交付；可恢复执行、正式执行入口和完整端到端验收仍按主计划核对。PON 截图路径已现场确认，但本次没有新增 PON 自动化接口。
