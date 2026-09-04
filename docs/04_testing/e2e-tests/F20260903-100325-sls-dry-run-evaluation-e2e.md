<!-- PDLC-TRACE -->
<!-- 功能ID: F20260903-100325 -->
<!-- 功能名称: sls-dry-run-evaluation -->
<!-- 阶段: 测试 -->
<!-- 创建时间: 2026-09-03T10:03:25+08:00 -->

# 本地端到端验证

1. 运行 `python3 scripts/sls_query.py --dry-run --service orders --query 'level:ERROR' --from 15m`，确认输出 `status: dry_run` 且不需要配置或凭据。
2. 使用外部运行器生成 JSONL，再运行 `python3 scripts/eval_contract.py --results <results.jsonl>`；全部匹配时返回 0，重复/未知/不匹配时返回非零。

真实 SLS 查询不属于本次验证范围。
