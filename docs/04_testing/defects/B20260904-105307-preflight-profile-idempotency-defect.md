<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-105307 -->
<!-- 功能名称: preflight-profile-idempotency -->
<!-- 阶段: review -->
<!-- 前置文档: docs/04_testing/defects/B20260904-102805-evidence-plan-integrity-defect.md -->
<!-- 创建时间: 2026-09-04T10:53:07+08:00 -->
<!-- 关系: resolves=F20260902-101243; extends=B20260904-102805 -->

# 工单预检 profile 与幂等性缺陷记录

## 根因分析

预检记录曾只绑定服务、SQL 与拆分参数，未绑定 resolved profile 或 PaaS 提交目标；同一用户私有目录中的记录可被另一 profile 使用。记录在成功或失败后仍可再次读取，确认 token 因而能够重复 POST。

## 影响范围

- 具有相同服务 group 的不同 profile 可能将已确认请求体发送到另一 PaaS API base。
- 同一确认 token 可创建重复工单；网络结果未知时重试风险更高。

## 修复方案

- 预检摘要与 token 绑定 resolved profile、PaaS API base、端点、响应标识和 apply contract；提交前逐项校验当前配置。
- token 使用随机 nonce；提交尝试开始时将计划原子移动为已消费状态。成功、失败和未知结果都不允许自动重试，必须先核对 PaaS 工单。

## 回归测试

- 红灯：regional profile 的预检可被 default profile 提交；apply contract 变化后仍可提交；同 token 可 POST 两次。
- 绿灯：新增三项回归测试分别拒绝跨 profile、契约变化和 token 重放。
- 全量验证：`python3 scripts/test_service_ops.py` 与 `python3 -m py_compile scripts/*.py`。
