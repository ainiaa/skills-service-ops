<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-112409 -->
<!-- 功能名称: task-action-profile-idempotency -->
<!-- 阶段: review -->
<!-- 前置文档: docs/04_testing/defects/B20260904-105307-preflight-profile-idempotency-defect.md -->
<!-- 创建时间: 2026-09-04T11:24:09+08:00 -->
<!-- 关系: extends=B20260904-105307 -->

# 已知工单操作 profile 与幂等性缺陷记录

## 根因分析

`approve`、`execute` 与 `recall` 使用了独立的确定性 token 分支，没有保存预检计划，也未绑定 resolved profile 或 action 契约。同 token 可连续发起多次 POST。

## 影响范围

- 共用 task API base 的不同 profile 可操作相同编号的工单。
- execute、approve 或 recall 可因重复运行同一命令而重复请求平台。

## 修复方案

- action 预检保存精确 task id、endpoint 与 body，并绑定 profile、task API base 和 action 契约。
- action token 使用随机 nonce，并在发起请求前原子消费；提交失败或状态未知时禁止重放。

## 回归测试

- 红灯：regional action 预检可被 default profile 执行；同一 execute token 可 POST 两次。
- 绿灯：新增测试拒绝跨 profile action，并拒绝已消费 token。
- 全量验证：`python3 scripts/test_service_ops.py` 与 `python3 -m py_compile scripts/*.py`。
