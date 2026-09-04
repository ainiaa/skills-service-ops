<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-153031 -->
<!-- 功能名称: sls-config-source -->
<!-- 阶段: tdd -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-04T15:30:31+08:00 -->
<!-- 关系: extends=B20260904-152149; relates_to=F20260902-101243 -->

# SLS 配置来源回归测试计划

## 场景

1. 私有 `sls` 配置中的 project、region、access_key、access_secret 可完整建立 SLS 连接参数。
2. 即使存在 `SLS_LOG_AK` 与 `SLS_LOG_SK`，缺失私有 AK/SK 时也必须被拒绝。
3. 配置模板包含 SLS AK/SK 占位字段。

## 红灯证据

旧 `get_credentials` 不接收配置对象，且会使用 Keychain 或 `SLS_LOG_AK`、`SLS_LOG_SK`，新增两项回归测试报错或失败。

## 绿灯命令

```bash
python3 -m unittest scripts.test_service_ops.LocalSlsQueryTests.test_sls_query_reads_all_sls_settings_from_private_config scripts.test_service_ops.LocalSlsQueryTests.test_sls_query_rejects_environment_credential_fallback
```
