<!-- PDLC-TRACE -->
<!-- 功能ID: B20260902-104525 -->
<!-- 功能名称: configuration-readiness -->
<!-- 阶段: review -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-02T10:47:40+08:00 -->
<!-- 关系: relates_to=F20260902-101243 -->

# 配置就绪与独立日志分析缺陷

## 根因

`setup.py` 只检查 PaaS Cookie 和依赖，没有检查查询接口的必填配置，因此会给出错误的就绪结论。`log_analyzer.py` 将可选的私有识别规则作为启动前置条件，导致标准 JSON 分析无法脱离私有配置使用。

## 影响范围

- `scripts/setup.py` 的 PaaS 就绪检查。
- `scripts/paas.py` 的查询契约校验。
- `scripts/log_analyzer.py` 的命令行入口。

## 修复方案

- 在共享 PaaS 模块中集中检查查询端点、字段契约和 prod/test 环境映射，并由就绪检查调用。
- 保持工单契约的显式执行时校验，不将其纳入通用 PaaS 就绪门槛。
- 配置文件不存在时，日志分析器使用空规则直接处理输入 JSON；配置存在时继续加载私有规则。

## 回归测试

`scripts/test_service_ops.py` 覆盖不完整与完整的 PaaS 查询配置、无私有配置的独立分析，以及存在私有规则时的分析行为。完整套件为 37 项通过。
