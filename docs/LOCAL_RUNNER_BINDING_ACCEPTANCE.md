# Local Runner Binding 离线验收

日期：2026-10-12。实施分支：codex/skill-execution。范围：批准的六项本机 Runner 接线任务。
本记录不代表真实 DUT 验收或正式发布批准；不包含 Task 10 前端、自动完整恢复、合并或推送。

## 验证方式

以测试数据库运行真实 Router → Service → Repository/Coordinator → Runtime/Registry/Adapter →
事实转换 → Evidence 存储和下载链路。只替换 SSH 客户端/通道、浏览器 surface、系统凭据存储、
网卡及网络 I/O。未使用当前现场地址、聊天账号密码或实际 keyring。

定向覆盖：

- 配置未知字段/重复 JSON 键/非法私网地址、URL、端口、指纹和引用；默认禁用。
- 成对凭据、隐藏输入、非交互拒绝、失败回滚及明确的 OS 故障恢复边界。
- 创建同事务保存固定绑定；配置修改与重启不漂移，不覆盖历史参数/设备/环境/标准快照。
- known_hosts 路径仍核对固定公钥；不匹配和连接失败关闭资源，不保存系统公钥。
- 白名单动作、未批准零变更、错误/过期 hash 拒绝；respond 不执行下一动作。
- 真实前缀、绑定网卡、缺失/多候选/地址变化及重复等待；不意外进入异常恢复。
- 标准事实来源、SN/FSP/Profile/online/match、同 WAN/VLAN 地址、当前探测及跨 epoch 隔离。
- 已注册目标如实记录缺失 autofind；不为了 PASS 修改标准。
- 注册/WAN 诊断收集、PPPoE 功能失败、选择器/指纹失败、Evidence SHA256 和下载归属。
- RESTORE 不支持完整 WAN 核验时 MANUAL_REQUIRED；中断配置动作重启后不自动重放。
- 本次绑定执行结束仍为 DRAFT；显式用户 LOCK 后原 Report/Archive 可用，HTML/ZIP hash 可验证。

## TDD 与兼容性

前三项分别先复现缺少配置接口、缺少绑定接口、固定公钥绕过/未清理连接。
Runtime/事实先确认模块缺失，再补边界测试复现地址消失与资源关闭异常。
API 先复现旧注入契约不兼容，再复现缺失凭据没有安全 outcome。
闭环测试复现自动 LOCK、选择器失败缺证据和重复接线交互进入恢复，并用最小修复通过。
原已满足的人工恢复阻塞、启动不重放及报告兼容样本仅作为兼容性测试，不声称经历 RED。
首次实施完成、独立审核前执行的验证（不是最终门禁）：

- 后端：python -m pytest backend/tests -q -p no:cacheprovider，
  basetemp=C:/Users/admin/Documents/Codex/lrb-tests/t6-full；522 passed（274.48 秒）。
- 前端：npm.cmd test -- --reporter=dot --maxWorkers=1；24 个文件、54 项通过（76.24 秒）。
- 生产构建：npm.cmd run build；TypeScript/Vite 构建通过。
- git diff --check：无空白错误。

前端仅复制已存在依赖供隔离验证；锁文件按换行规范化后完全相同，没有安装或修改依赖。
独立审核已执行，发现五项 Important：目标身份混用、认证晚于指纹校验、
PNG 凭据遮挡不足、PC/WAN 归属未经证明、无法识别的读输出误判为功能失败。
一项 Minor 暂缓：本机 enrollment CLI 未区别显示需人工恢复的安全错误码；
异常 OS 故障后应按 setup 说明重新登记整对凭据。

## 独立审核修复（2026-10-12）

本次先新增真实动作、真实 Paramiko 连接流程（仅套接字/Transport 替身）、
实际 Playwright 页面和 Runtime 回归测试；11 项首先失败，复现五项问题。
再补一项 PPPoE 凭据供 Web 脱敏测试，首先因缺少该值失败。
修复在同一轮完成，未另开复审、未操作现场：

1. Snapshot 接受前核对 SN/FSP/ONT-ID，拒绝查询其他 ONU 的 WAN；批准后、
   每项变更前再次核对身份，注册核对未注册/空闲 ID/autofind，删除 service-port 核对归属。
2. 同一 SSH 连接先按 Paramiko 原机制核验 known_hosts，再校验固定指纹，
   最后进行密码认证；错误 pin 零认证尝试，匹配 pin 才认证，不保存系统公钥。
3. PNG 之前遮挡普通文本、readonly 控件和相关子帧；Web 同时读取冻结引用对应的
   PPPoE pair 供脱敏。无法建立遮挡时拒绝截图，不将未知像素内容标成 redacted。
4. 去掉唯一活跃 WAN + 源地址 Ping 推导的归属 True。保留诊断数据/证据，
   不生成标准联网 PASS；接线等待不会重新使用旧来源生成归属。
   **当前不具备端到端联网 PASS 的独立路径证明，不宣称全流程成功验收。**
5. 明确的空 autofind/WAN 输出可作为真实负面/空来源；权限错误、未知格式及
   不可识别 WAN 状态返回 BLOCKED，不生成 DUT 不匹配 False。

旧的离线成功期望已按上述安全边界纠正；不是降低标准或补造路径证明。
注册/地址/ONU Ping/PC 诊断仍可收集，标准联网项缺来源；
若已存在明确功能失败，原 evaluator 保留 FAIL，不将其伪装成环境成功。
修复后完整验证：

- 后端：python -m pytest backend/tests -q -p no:cacheprovider，
  basetemp=C:/Users/admin/Documents/Codex/lrb-tests/review-full1；535 passed（278.68 秒）。
- 前端：npm.cmd test -- --reporter=dot --maxWorkers=1；24 个文件、54 项通过（76.30 秒）。
- 生产构建：npm.cmd run build；TypeScript/Vite 构建通过。
- git diff --check：无空白错误。没有业务表迁移、依赖更新或前端业务改动。

独立审核由外部只读 reviewer 完成；修复后的验证由作者执行，不将其写成第二次独立审核。
安全修复可提交留在隔离分支；**端到端联网 PASS/真实设备验收门禁仍 HOLD**，
须先评审并建立独立、当前的实际路径/隔离证明。真实 DUT 仍为 NOT_EXECUTED。

## 数据及安全边界

没有新增表、Migration、依赖或前端业务代码。runtime_binding 是现有 plugin_snapshot 的新增子对象。
只包含目标/访问引用及配置 hash，不包含凭据值；按敏感实验室元数据管理备份。
实际配置、生成证据、数据库、ZIP、缓存与构建产物均不属于提交。
低层旧离线 Coordinator 的自动锁定行为保留兼容；新持久化绑定会话不自动锁定。

失败不会伪装功能成功。WAN 功能 FAIL 后可能跳过后续收集，导致证据不齐：
functional_verdict 保留 FAIL，最终交付结果可为 BLOCKED，不捏造缺失证据。
完整恢复和无法证明的 PC/WAN 归属不在成功承诺内；默认系统 DNS 不计作 ONU 归属证明。

## 真实设备验收

**NOT_EXECUTED**：未登录 ONU/OLT、未扫描 IP、未读取现场 SSH 公钥、未注册或下发 WAN。

需要另行授权并重新核对 DUT 型号/版本/SN、OLT 地址/指纹、F/S/P/ONT ID、Profile/VLAN、
ONU Web 目标、实际网卡及本机凭据登记。先只读检查，再逐项确认配置影响、恢复责任和 preview_hash；
创建新 Run，不修改旧记录。现场结果须单独记录，不能从离线成功推断真实业务 PASS。
