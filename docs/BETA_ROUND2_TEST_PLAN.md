# Beta Round 2 测试计划（用例库扩充）

> 目标：Round 1 只有 3 个用例且从未产生 FAIL，检验力不足。本轮补充异常恢复、
> 边界与服务类用例，检验真实抓缺陷的能力。
> 用例绑定 `device_type=ONU`，不绑定具体型号——更换 DUT 无需改用例。

## 环境与凭据

- OLT：华为 MA5800-X7 或同类 GPON OLT（管理地址见环境快照）
- 测试设备：可调光衰减器、光功率计、Wi-Fi 终端、可断电的 ONU 电源
- 凭据：一律通过应用凭据管理（keyring）录入，环境参数中以
  `credential:<引用名>` 引用；**禁止明文写入环境参数**（模型层会拒绝）。

## 用例清单（7 个新增，随 `seeds/round2_cases.json` 发布）

| 用例 | 优先级 | 验证点 | 需要的额外设备 |
|---|---|---|---|
| R2-PON-002 光路中断恢复 | P1 | LOS 告警→自动恢复 O5 | 可断尾纤 |
| R2-PON-003 光功率临界 | P2 | 实测灵敏度 ≥ -28 dBm | 衰减器+光功率计 |
| R2-PON-004 断电重启 | P1 | 注册/配置/业务自动恢复 | 可控电源 |
| R2-WAN-002 PPPoE 重拨 | P1 | 会话中断自动重拨 | BRAS 踢线手段 |
| R2-WAN-003 PPPoE 认证失败 | P2 | 错误凭据持续重试不崩溃 | — |
| R2-SVC-001 WLAN 连通 | P2 | 2.4G/5G 双频外网可达 | Wi-Fi 终端 |
| R2-MGT-001 TR069 状态 | P3 | 管理通道注册正常 | ACS（可选） |

## 执行顺序建议

1. 先跑 P1（R2-PON-002 / R2-PON-004 / R2-WAN-002）——最可能暴露真实缺陷
2. 再跑 P2/P3
3. 每个用例产生 BLOCKED/FAIL 时：登记缺陷（附截图+日志证据）、
   回归验证通过后才允许 RESOLVED→CLOSED（时间戳自动记录）

## 导入方式

```bash
# 干跑查看
python tools/seed_test_cases.py <workbench.db> --dry-run
# 实际导入（跳过已存在的 case_code，可重复执行）
python tools/seed_test_cases.py <workbench.db>
```

导入后在应用内按项目勾选用例即可执行。

## 证据要求

- 每个用例至少 1 份 LOG + 1 份 SCREENSHOT
- 文本证据上传后自动解析（OLT CLI / PON 状态 / ping 诊断），
  报告中显示自动判定徽章（ONT 在线、O5、光功率、丢包、时延）
- 截图证据在报告 HTML 中内嵌展示
