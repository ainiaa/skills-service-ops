<!-- PDLC-TRACE -->
<!-- 功能ID: F20260902-101243 -->
<!-- 功能名称: service-ops-governance -->
<!-- 阶段: 测试 -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-02T10:12:43+08:00 -->

# service-ops 运维治理测试计划

## 1. 测试范围

本次是文档型功能，没有新增运行代码；复用 `scripts/test_service_ops.py` 对已实现行为进行回归验证。

| 验收标准 | 覆盖测试 | 预期 |
|---|---|---|
| 截断证据保留 | `test_analyzer_sorts_timeline_and_preserves_evidence_completeness` | summary 包含 `truncated_services` |
| SLS 截断传递 | `test_trace_fetch_propagates_json_truncation_metadata` | fetcher 保留 `truncated: true` |
| PaaS 依赖隔离 | `test_missing_dependencies_reports_all_runtime_modules` | `paas` 不要求 SLS SDK |
| PaaS 就绪契约 | `test_check_readiness_rejects_incomplete_paas_query_contract`、`test_check_readiness_accepts_complete_paas_query_contract` | 缺少端点、字段或环境映射时失败；完整配置时通过 |
| 独立日志分析 | `test_analyzer_cli_works_without_private_config`、`test_analyzer_cli_uses_optional_log_analysis_config` | 缺少私有配置仍可分析 JSON；存在配置时应用识别规则 |
| 多 profile 排障 | `test_trace_fetch_records_the_resolved_profile_for_analysis`、`test_analyzer_cli_uses_the_profile_embedded_by_the_collector` | 采集与分析使用同一 profile |
| 截断与脱敏 | `test_sls_query_always_marks_a_full_page_as_truncated`、`test_redacts_sensitive_log_mapping_values`、`test_analyzer_redacts_sensitive_message_content` | 各输出模式保留截断证据；SLS 字段与摘要不泄露通用凭据 |
| 工单安全边界 | `ApplyTests` | 无 WHERE DML 和危险 DDL 被拒绝 |

## 2. 红绿状态说明

功能实现已在本次文档补齐前完成，未修改生产逻辑，因此不存在新的红灯测试或实现阶段。以上既有回归用例在当前代码上应全部为绿；若任何用例失败，文档不得宣称与实现一致。

## 3. 自审记录

- 自审时间：2026-09-02T10:12:43+08:00
- 验收标准覆盖：4/4。
- 正常、边界、异常：分别覆盖成功汇总、截断边界、缺失依赖和危险 SQL。
- 结论：通过。
