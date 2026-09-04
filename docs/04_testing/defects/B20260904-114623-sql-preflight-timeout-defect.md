<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-114623 -->
<!-- 功能名称: sql-preflight-timeout -->
<!-- 阶段: review -->
<!-- 前置文档: docs/04_testing/defects/B20260904-113446-sql-query-preflight-safety-defect.md -->
<!-- 创建时间: 2026-09-04T11:46:23+08:00 -->
<!-- 关系: extends=B20260904-113446; relates_to=F20260902-101243 -->

# SQL 边界、预检隐私与 SLS 超时缺陷记录

## 根因分析

危险函数检查基于移除反引号标识符后的 SQL，故反引号调用可绕过；只读策略也未限制会话变量赋值和 `LAST_INSERT_ID(expr)`。token 消费后仍保留完整预检 JSON。TraceId 采集的子进程和 SDK 请求均未指定超时。

## 影响范围

- 数据验证和 Excel 导出可能运行有锁、文件读取、资源消耗或会话副作用的 SELECT。
- 消费后的本地文件会保留 SQL、请求体及工单元数据直到之后某次清理。
- SLS 网络异常可能长期阻塞排障流程。

## 修复方案

- 在独立的安全解析视图中保留反引号函数标识，并拒绝危险函数、会话变量赋值与 `LAST_INSERT_ID`。
- 原子领取预检后保留内存中的提交内容，但立即将落盘文件缩减为仅含 `consumed_at` 的标记。
- 为 SLS SDK 设置 30 秒单请求超时，为 TraceId 子进程设置 60 秒总超时并返回受控错误。

## 回归测试与验证

- 红灯：反引号函数、会话副作用 SQL、完整已消费计划和子进程超时均未受控。
- 绿灯：新增覆盖 SQL 三条路径、消费文件脱敏、SDK timeout、子进程 timeout 的回归测试。
- 全量验证：`python3 scripts/test_service_ops.py`（116 通过）、`python3 -m py_compile scripts/*.py`、SQL/预检隐私探针与 `sls_query.py --dry-run`。
- 真实 PaaS/SLS 集成和外部 Agent 评测仍需授权的私有凭据环境；本次未发起真实网络请求。
