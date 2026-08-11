# Sprint 10 History & Evidence Efficiency

## 范围

- TestRun 可读编号与历史回填
- 服务端组合筛选和分页
- 2–5 Run 的 Snapshot 结果比较
- Evidence 批量上传与同 Run 多结果关联
- Report 展开共享 Evidence，Archive 去重打包

## 完整性规则

- 历史 Run、RunResult 与 Snapshot 不修改。
- Comparison 仅在请求期间计算，不写入数据库。
- Evidence 多关联只允许同一 Run 内的 DRAFT Result。
- 任一关联 Result LOCKED 后，共享 Evidence 不可删除。
- 已生成 Report/Archive 不回写；新 Archive 对共享文件按 Evidence ID 去重。

## 验证命令

```text
python -m pytest backend/tests -q
npm.cmd test -- --reporter=dot --maxWorkers=1
npm.cmd run build
git diff --check
git status --short
```
