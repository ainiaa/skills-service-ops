<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-153812 -->
<!-- 功能名称: no-environment-credentials -->
<!-- 阶段: tdd -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-04T15:38:12+08:00 -->
<!-- 关系: extends=B20260904-153031; relates_to=F20260902-101243 -->

# 无环境变量凭据回归测试计划

## 场景

1. PaaS Cookie 在 Keychain 超时后从已解析私有配置读取，即使 `PAAS_COOKIE` 存在也不得使用。
2. 测试库密码在 Keychain 未命中时从已解析私有配置读取，即使 `TEST_DB_PASSWORD` 存在也不得使用。
3. SLS AK/SK、PaaS Cookie、测试库密码均以 Keychain 优先、配置文件兜底。

## 红灯证据

旧实现使用 `PAAS_COOKIE` 与 `TEST_DB_PASSWORD` 环境变量，新增回归测试因函数签名不支持配置兜底而报错。

## 绿灯命令

```bash
python3 -m unittest scripts.test_service_ops.DatabaseRoutingTests.test_keychain_timeout_is_bounded_and_falls_back_to_private_config scripts.test_service_ops.DatabaseRoutingTests.test_paas_credentials_fall_back_to_the_resolved_private_config scripts.test_service_ops.LocalSlsQueryTests.test_sls_keychain_credentials_take_precedence_over_private_config
```
