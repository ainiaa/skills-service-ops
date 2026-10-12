<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-113446 -->
<!-- 功能名称: sql-query-preflight-safety -->
<!-- 阶段: review -->
<!-- 前置文档: docs/04_testing/defects/B20260904-112409-task-action-profile-idempotency-defect.md -->
<!-- 创建时间: 2026-09-04T11:34:46+08:00 -->
<!-- 关系: extends=B20260904-112409; relates_to=F20260902-101243 -->

# SQL 查询与预检生命周期缺陷记录

## 根因分析

共享 SELECT 守卫只限制语法级写入和锁定子句，未拒绝可获取锁、消耗连接资源或读取服务器文件的函数。DDL/DML 与 task action 的确认路径也在验证 Cookie 前消费预检，因此本地凭据缺失会使尚未发送请求的计划失效。消费后的计划没有保留期。

## 影响范围

- `db_query.py` 与 `db_export.py` 可将危险函数交给测试库或 PaaS 查询端点。
- 缺失 PaaS Cookie 时，用户需要重新预检才能提交完全相同的计划。
- 用户私有目录会无限保留已消费计划中的 SQL 与工单元数据。

## 修复方案

- 在共享守卫中拒绝 `GET_LOCK`、`RELEASE_LOCK`、`SLEEP`、`BENCHMARK` 与 `LOAD_FILE`。
- 两类确认路径均先读取 Cookie，再原子消费预检计划。
- 在创建新预检时清理超过七天的 `.submitted` 记录；未提交的计划不自动删除。

## 回归测试与验证

- 红灯：五种危险函数被错误视为只读；缺 Cookie 后计划被标记为已提交；历史记录不能清理。
- 绿灯：新增回归覆盖，验证危险函数拒绝、同名字面量和列别名不误拒绝、apply/action 凭据失败保留计划与七天清理边界。
- 全量验证：`python3 scripts/test_service_ops.py`（111 通过）、`python3 -m py_compile scripts/*.py`、`python3 scripts/sls_query.py --dry-run --service orders --query 'TraceId: abc123'`。
- 外部 PaaS/SLS 集成仍需在已授权的私有配置和凭据环境执行；本次没有发起真实网络请求。
