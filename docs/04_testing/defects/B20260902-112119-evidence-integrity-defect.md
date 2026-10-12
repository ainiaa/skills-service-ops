<!-- PDLC-TRACE -->
<!-- 功能ID: B20260902-112119 -->
<!-- 功能名称: evidence-integrity -->
<!-- 阶段: review -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-02T11:21:19+08:00 -->
<!-- 关系: relates_to=F20260902-101243 -->

# 排障证据完整性与脱敏缺陷

## 根因

采集器解析 profile 后没有把它传给分析器，非 default profile 可能使用 default 的私有规则。`sls_query.py --analysis` 对达到行数上限的查询抑制了截断元数据。采集和分析路径都只有文本约束，没有在代码中对敏感字段实施脱敏。

## 影响范围

- 非 default profile 的关联服务与实体识别。
- 原生 SLS `--analysis` 输出的证据完整性。
- 本地采集 JSON 与分析摘要中的常见凭据或部署侧敏感标识。

## 修复方案

- 采集结果写入已解析 profile；分析器优先使用它，并允许 `--profile` 显式覆盖。
- 所有输出模式在结果达到 `limit` 时保留 `truncated: true`。
- SLS 查询、采集器和分析摘要均遮蔽常见凭据；采集器仅保留排障需要的字段，分析摘要另外从私有配置读取业务脱敏正则。
- 收紧 Skill 的自动触发范围，按能力说明初始化检查；关联服务仅经用户确认后扩展采集。

## 回归测试

`scripts/test_service_ops.py` 覆盖多 profile 贯通、分页截断、SLS 原始字段和摘要的通用凭据脱敏、私有脱敏正则及无效规则。完整套件为 46 项通过。
