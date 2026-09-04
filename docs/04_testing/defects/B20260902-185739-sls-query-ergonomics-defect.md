<!-- PDLC-TRACE -->
<!-- 功能ID: B20260902-185739 -->
<!-- 功能名称: sls-query-ergonomics -->
<!-- 阶段: review -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-02T18:57:39+08:00 -->
<!-- 关系: resolves=F20260902-101243 -->

# sls-query-ergonomics 缺陷记录

## 根因分析

普通 SLS 查询和 TraceId 采集在未指定时间范围时默认查询最近 1 天，容易扩大扫描范围、增加噪声并降低排障效率。Skill 缺少按意图收集输入的简短入口，也没有将聚合分析与普通原始日志检索区分为先计划、后执行的安全流程。触发回归只有执行后行为场景，缺少激活、追问与拒绝的独立契约。

## 修复方案

- 将 `sls_query.py` 与 `sls_log_fetcher.py` 的默认时间范围收紧为最近 15 分钟。
- 为趋势、Top-N、分组、P95 和分布增加只读查询计划参考；超过 1 小时先确认范围。
- 在 Skill 增加按意图的最小输入卡片，并新增 `evals/triggers.json` 与结构回归测试。

## 回归测试

- 红灯：默认范围和触发契约的 3 项新增测试失败。
- 绿灯：全量 75 项 Python 单元测试通过。
- 附加验证：Python 编译、Shell 语法、两个 eval JSON 和 Skill 结构校验通过。
