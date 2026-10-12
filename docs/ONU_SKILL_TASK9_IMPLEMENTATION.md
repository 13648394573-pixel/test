# ONU Skill Task 9 实施记录

日期：2026-10-12。基线：b4160c7。范围仅 Task 9 执行 API、启动恢复与安全响应，不进入 Task 10–12。

## 实施边界

现有参数只有目标及访问引用，没有正式的本机目标解析和成对凭据映射配置。API 不猜测设备地址，不将引用当作账号密码，不复用现场测试硬编码。受控 Runtime 通过本机应用构造时注入；默认未配置时 advance/respond 返回 409，不触发任何动作、不修改会话。真实适配器装配和标准事实生成仍需明确配置方案及联调，不能宣称已完成真实设备自动化接入。

接口只在本机绑定下使用，拒绝跨站浏览器请求。读取及响应采用安全投影，不暴露凭据、原始命令、原始事件 payload 或本机存储路径。运行仍保持 DEVELOPMENT。

## 接口与恢复

接口前缀 `/api/skill-executions`：

- POST 空路径：创建执行。
- GET `/{session_id}`：读取安全执行视图。
- POST `/{session_id}/advance`：推进执行。
- POST `/{session_id}/interactions/{interaction_id}/respond`：提交明确确认及精确 preview hash。
- GET `/{session_id}/evidence`：读取经完整性验证的证据元数据。
- GET `/{session_id}/evidence/{evidence_id}/download`：校验归属、脱敏标志、大小及 SHA256 后返回已验证的字节，使用安全文件名和 no-store。

旧附件下载地址只对 DEVELOPMENT/ONU_LOCAL_RUNNER 证据重定向到上述受保护接口，普通 V1 附件行为保持不变。启动扫描中断的执行并进入恢复处理，保留 WAITING_OPERATOR；不调用设备动作。不存在返回 404、状态冲突返回 409、参数错误返回 422、文件缺失返回 410。错误响应避免回显敏感输入。

## 验证与审核

新增 API 测试覆盖创建、冲突、审批重放、默认禁用、敏感信息投影、证据篡改/缺失、旧下载别名及启动恢复。通过测试先行复现并修复下载绕过与原始文件名暴露。独立审核无 Critical 或剩余 Important 项。

原提交 b73c725 验证：`python -m pytest backend/tests/test_skill_execution_api.py -q`，24 passed；全量 `python -m pytest backend/tests -q -p no:cacheprovider --basetemp=C:/Users/admin/Documents/Codex/t9-full-final-1012b`，419 passed（295.61 秒）。测试前将 PYTHONPATH 指向本 worktree 的 backend，避免使用 main 的可编辑安装。`git diff --check` 无空白错误。

原审核暂缓的两项 Minor 已在本次整改：Origin 解析纳入校验异常处理，畸形 Origin 返回 403，同源判断同时比较 scheme 和 authority；旧下载别名先查询元数据并重定向，不再提前处理文件路径。文件缺失/非法路径由受保护接口统一返回 410/409，跨源请求返回 403，并带 no-store。普通 V1 附件仍保留原下载处理。

整改采用测试先行：新增回归测试在修复前 4 failed、1 passed，失败分别复现异常解析、跨协议放行和旧入口提前处理路径。修复后 API 测试 29 passed（38.84 秒）。本次不接入 Runtime、不合并、不推送；整改变更保留在隔离分支供审核。

整改全量验证：`python -m pytest backend/tests -q -p no:cacheprovider --basetemp=C:/Users/admin/Documents/Codex/t9r-full1012`，424 passed（257.27 秒），包含已有附件下载兼容性测试。`git diff --check` 无空白错误；main 保持 0e915f22 且干净。

整改独立只读审核结论：四文件补丁无 Critical/Important/Minor 项，可以提交。审核未执行测试，测试结果由实施方验证。真实 Runner、设备操作、多进程、前端及完整 Origin 语法规范化不属于此次两项修复的验收范围；这些未作通过声明。

提交前再次全量验证：`python -m pytest backend/tests -q -p no:cacheprovider --basetemp=C:/Users/admin/Documents/Codex/t9r-commit-full1012`，424 passed（260.00 秒）。修复提交只固化上述四文件，不合并 main、不推送远端、不开始 Task 10。

无迁移、依赖及前端变更；不进行 ONU/OLT 操作。前端测试和构建本次未重跑。进程内锁仅面向当前单进程本机部署，多进程执行不在本次验收范围。真实目标解析、成对凭据映射、适配器事实生成及完整 WAN 恢复仍待联调。
