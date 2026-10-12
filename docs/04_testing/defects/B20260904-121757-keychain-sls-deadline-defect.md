<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-121757 -->
<!-- 功能名称: keychain-sls-deadline -->
<!-- 阶段: review -->
<!-- 前置文档: docs/04_testing/defects/B20260904-114623-sql-preflight-timeout-defect.md -->
<!-- 创建时间: 2026-09-04T12:17:57+08:00 -->
<!-- 关系: extends=B20260904-114623; relates_to=F20260902-101243 -->

# Keychain 与 SLS 查询 deadline 缺陷记录

## 根因分析

macOS Keychain 的 `security` 子进程没有超时，异常系统状态会无限阻塞凭据读取。SLS 虽限制单次 SDK 请求为 30 秒，但多页读取没有总时限；SDK 依赖也没有版本边界，后续升级可能改变该超时配置的兼容性。

## 影响范围

- Keychain 卡住时，PaaS Cookie 读取无法及时回退到同 profile 的环境变量。
- 长分页或持续返回数据的 SLS 查询可能超过运维操作可接受的总时长。
- 未约束的 SDK 升级可能使已验证的 `client.timeout` 行为漂移。

## 修复方案

- 将 Keychain 调用限制为 10 秒；超时或系统错误时返回空值，由既有逻辑回退到同 profile 环境变量。
- 在共享 `fetch_logs` 分页路径设置 60 秒总 deadline，并保留 30 秒 SDK 单请求超时。
- 将 `aliyun-log-python-sdk` 约束为已验证的 `>=0.9.50,<0.10`。

## 回归测试与验证

- 红灯：Keychain 超时会直接抛出，SLS 缺少分页总 deadline，SDK 依赖没有兼容边界。
- 绿灯：新增 Keychain 超时回退、SLS 分页总 deadline 与 SDK 版本约束测试。
- 全量验证：`python3 scripts/test_service_ops.py`（119 通过）、`python3 -m py_compile scripts/*.py`、`python3 scripts/sls_query.py --dry-run --service orders --query 'TraceId: abc123'`。
- 真实 PaaS/SLS 集成和外部 Agent JSONL 评测仍需授权的私有环境；本次未发起真实网络请求。
