<!-- PDLC-TRACE -->
<!-- 功能ID: B20260902-114930 -->
<!-- 功能名称: log-safety-and-profile -->
<!-- 阶段: review -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-02T11:49:30+08:00 -->
<!-- 关系: relates_to=F20260902-101243 -->

# 日志安全与自定义 Profile 缺陷

## 根因

私有 `log_analysis.redaction_patterns` 仅在分析摘要加载，SLS 原始输出仍只使用通用凭据脱敏；日志识别正则和采集 JSON 的结构直到运行到深层处理才报错；数据库工具的命令行参数把 profile 硬编码为模板中的两个名称。Trace 示例也未说明清理包含日志证据的临时目录。

## 影响范围

- 原始 SLS JSON、Trace 采集结果和分析摘要的业务敏感标识。
- 配置正则错误或手工输入不合法 JSON 时的错误可读性。
- 使用新增私有 profile 的数据库验证、导出与显式工单命令。
- 本地 Trace 排障完成后的临时证据文件。

## 修复方案

- 在 `paas.py` 集中校验并编译日志规则，所有 SLS 输出复用该规则链路递归脱敏；分析器和 SLS 就绪检查也使用同一校验。
- 分析器在访问日志字段前校验采集 JSON，向调用者返回明确错误。
- 移除三个数据库脚本的 profile 枚举限制，仍由私有配置决定 profile 是否存在。
- Trace 示例明确在读取并报告结果后删除 `mktemp` 创建的目录。

## 回归测试

`scripts/test_service_ops.py` 新增私有规则覆盖原始日志、无效规则和结构、SLS 就绪检查、自定义 profile 的数据库命令行回归。完整套件 51 项通过。
