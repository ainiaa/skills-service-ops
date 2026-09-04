<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-122754 -->
<!-- 功能名称: sls-full-deadline -->
<!-- 阶段: review -->
<!-- 前置文档: docs/04_testing/defects/B20260904-121757-keychain-sls-deadline-defect.md -->
<!-- 创建时间: 2026-09-04T12:27:54+08:00 -->
<!-- 关系: extends=B20260904-121757; relates_to=F20260902-101243 -->

# SLS 全链路 deadline 与凭据说明缺陷记录

## 根因分析

60 秒 deadline 只覆盖日志分页，索引探测和 `--doctor` 的元数据、索引、读权限探针未共享同一时钟，实际命令可能超过文档承诺。使用说明还将测试库密码描述为仅存 Keychain，而实现与架构均支持同 profile 环境变量回退。

## 影响范围

- 索引服务或 doctor 任一步缓慢响应时，SLS 命令可能超过 60 秒才返回。
- 使用 `TEST_DB_PASSWORD` 的部署会被错误的操作说明误导。

## 修复方案

- 从真实 SLS 查询开始创建 deadline；每次 SDK 调用按剩余时间收紧 `client.timeout`，并在调用前后检查 deadline。
- 索引探测、doctor 和分页复用同一 deadline；超时返回受控缩小范围提示。
- 将 README 与 Skill 的测试库密码来源统一为 Keychain 或同 profile 环境变量。

## 回归测试与验证

- 红灯：索引探测耗尽 deadline 后命令仍继续执行。
- 绿灯：新增索引探测与 doctor deadline 回归用例；现有分页 deadline 用例继续通过。
- 全量验证：`python3 scripts/test_service_ops.py`、`python3 -m py_compile scripts/*.py`、`python3 scripts/sls_query.py --dry-run --service orders --query 'TraceId: abc123'`。
- 授权私有环境中的真实 PaaS/SLS 集成和外部 Agent JSONL 评测仍需单独执行；本次未发起真实网络请求。
