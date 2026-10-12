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
- 新注册成功、PPPoE 功能失败、选择器/指纹失败、Evidence SHA256 和下载归属。
- RESTORE 不支持完整 WAN 核验时 MANUAL_REQUIRED；中断配置动作重启后不自动重放。
- 本次绑定执行结束仍为 DRAFT；显式用户 LOCK 后原 Report/Archive 可用，HTML/ZIP hash 可验证。

## TDD 与兼容性

前三项分别先复现缺少配置接口、缺少绑定接口、固定公钥绕过/未清理连接。
Runtime/事实先确认模块缺失，再补边界测试复现地址消失与资源关闭异常。
API 先复现旧注入契约不兼容，再复现缺失凭据没有安全 outcome。
闭环测试复现自动 LOCK、选择器失败缺证据和重复接线交互进入恢复，并用最小修复通过。
原已满足的人工恢复阻塞、启动不重放及报告兼容样本仅作为兼容性测试，不声称经历 RED。
本次已执行的验证：

- 后端：python -m pytest backend/tests -q -p no:cacheprovider，
  basetemp=C:/Users/admin/Documents/Codex/lrb-tests/t6-full；522 passed（274.48 秒）。
- 前端：npm.cmd test -- --reporter=dot --maxWorkers=1；24 个文件、54 项通过（76.24 秒）。
- 生产构建：npm.cmd run build；TypeScript/Vite 构建通过。
- git diff --check：无空白错误。

前端仅复制已存在依赖供隔离验证；锁文件按换行规范化后完全相同，没有安装或修改依赖。
独立审核尚待执行，不能将测试通过当作审核通过。

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
