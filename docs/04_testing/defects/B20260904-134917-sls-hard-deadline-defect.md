<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-134917 -->
<!-- 功能名称: sls-hard-deadline -->
<!-- 阶段: review -->
<!-- 前置文档: docs/04_testing/defects/B20260904-122754-sls-full-deadline-defect.md -->
<!-- 创建时间: 2026-09-04T13:49:17+08:00 -->
<!-- 关系: extends=B20260904-122754; relates_to=F20260902-101243 -->

# SLS SDK 重试越过 deadline 缺陷记录

## 根因分析

SDK 的 `timeout` 约束单次 HTTP 请求，但 SDK 会对瞬态失败重试。原实现仅在 SDK 方法返回后检查 deadline，重试循环因此可能在 60 秒之后才回到本地代码。

## 影响范围

- 索引探测、doctor 和日志分页遇到可重试网络错误时，真实 SLS 命令可能显著超过承诺的 60 秒。

## 修复方案

- 在 macOS/Unix 主线程使用 `SIGALRM` 的进程级定时器包裹真实查询，deadline 到期时直接中断 SDK 重试。
- 不支持该定时器的平台拒绝真实查询，避免将软 timeout 描述为硬 60 秒。

## 回归测试与验证

- 红灯：不存在硬 deadline，上层无法中断阻塞 SDK 调用。
- 绿灯：10ms deadline 会中断 100ms 阻塞等待；原有索引、doctor 和分页 deadline 测试继续通过。
- 全量验证：`python3 scripts/test_service_ops.py`、`python3 -m py_compile scripts/*.py`、`python3 scripts/sls_query.py --dry-run --service orders --query 'TraceId: abc123'`。
- 真实 PaaS/SLS 集成与外部 Agent JSONL 评测仍需授权私有环境；本次未发起真实网络请求。
