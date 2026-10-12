<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-102805 -->
<!-- 功能名称: evidence-plan-integrity -->
<!-- 阶段: review -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-04T10:28:05+08:00 -->
<!-- 关系: resolves=F20260902-101243; extends=F20260903-100325 -->

# 证据与预检计划完整性缺陷记录

## 根因分析

SLS 截断判断只接受“返回数等于 limit”，未覆盖单次 SDK 批次返回数超过 limit 后本地仍只输出 limit 条的情况。工单确认指纹只绑定 SQL 等请求摘要，提交时重新生成工单拆分与生产执行窗口，因此已确认的预检计划可能与实际提交内容不一致。

## 影响范围

- TraceId 排障可能遗漏 `truncated_services`，把不完整日志证据误作完整证据。
- 变更执行人可以用同一确认指纹改变 `--batch-size`，或在稍后提交时使用重新计算的生产执行窗口。

## 修复方案

- 截断判断改为“返回数达到或超过 limit”即输出 `truncated: true`。
- 预检将完整 ticket body 写入 `~/.service-ops/preflights/` 下的权限为 `600` 的计划记录；提交验证不变的请求摘要，并只提交已保存的 ticket body。

## 回归测试

- 红灯复现：`truncation_metadata(101, 100)` 在旧实现中返回空值；旧实现也允许预检 `--batch-size 1`、提交 `--batch-size 2` 使用同一 token。
- 绿灯：新增测试验证超过 limit 的截断标记、拒绝变更工单拆分、提交复用原预检 ticket body。
- 全量验证：`python3 scripts/test_service_ops.py` 与 `python3 -m py_compile scripts/*.py`。
