<!-- PDLC-TRACE -->
<!-- 功能ID: F20260902-101243 -->
<!-- 功能名称: service-ops-governance -->
<!-- 阶段: 测试 -->
<!-- 前置文档: docs/04_testing/unit-tests/F20260902-101243-service-ops-governance-test-plan.md -->
<!-- 创建时间: 2026-09-02T10:12:43+08:00 -->

# service-ops 端到端验证清单

真实 SLS/PaaS 环境需要用户凭据与授权，本次不执行生产或外部系统操作。

1. 配置测试账户后运行 `setup.py --check --capability sls`，确认仅报告 SLS 相关缺失项。
2. 使用受控测试 TraceId 执行 fetcher 与 analyzer，确认截断时最终报告标记“证据不完整”。
3. 在普通排障请求中确认不会进入工单流程；仅显式 `$skills-service-ops` 且明确工单意图后才可预检。

状态：未执行（依赖人工授权的集成环境）。
