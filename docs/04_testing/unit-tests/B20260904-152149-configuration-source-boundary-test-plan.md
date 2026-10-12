<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-152149 -->
<!-- 功能名称: configuration-source-boundary -->
<!-- 阶段: tdd -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-04T15:21:49+08:00 -->
<!-- 关系: extends=B20260904-145318; relates_to=F20260902-101243 -->

# 非敏感配置来源回归测试计划

## 场景

1. `SERVICE_OPS_PROFILE=regional` 存在时，未传 `--profile` 仍选择 `default`。
2. `SLS_LOG_PROJECT`、`SLS_LOG_REGION`、`SLS_LOG_ENDPOINT` 存在时，缺失私有 SLS 配置仍被拒绝。
3. 私有配置提供 SLS project/region 时，其值可被解析。

## 红灯证据

新增测试运行时，旧实现分别读取 `regional` 和 SLS 环境变量，两个断言失败。

## 绿灯命令

```bash
python3 -m unittest scripts.test_service_ops.DatabaseRoutingTests.test_runtime_profile_does_not_come_from_environment scripts.test_service_ops.DatabaseRoutingTests.test_sls_connection_does_not_fall_back_to_environment_configuration
```
