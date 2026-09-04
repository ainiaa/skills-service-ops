<!-- PDLC-TRACE -->
<!-- 功能ID: F20260903-100325 -->
<!-- 功能名称: sls-dry-run-evaluation -->
<!-- 阶段: 设计 -->
<!-- 前置文档: docs/01_requirements/prd/F20260903-100325-sls-dry-run-evaluation-prd.md -->
<!-- 创建时间: 2026-09-03T10:03:25+08:00 -->

# SLS 查询计划与触发评测设计

`sls_query.py` 先完成纯本地的参数归一化：profile、查询、时间范围和 logstore。若指定 `--dry-run`，立即序列化计划并返回；仅真实执行分支才加载配置、凭据、SDK 和 SLS 客户端。

`eval_contract.py` 读取版本化公开契约与外部 JSONL。每个契约 ID 至多出现一次；unknown、duplicate、missing、action 不匹配和 route 不匹配均返回非零状态。判定器不调用模型，也不保存运行结果。

## 失败处理

- 参数或时间范围无效：由命令参数错误拒绝。
- JSONL 或契约不可读：受控参数错误。
- 评测失败：打印结构化原因并以非零退出。
