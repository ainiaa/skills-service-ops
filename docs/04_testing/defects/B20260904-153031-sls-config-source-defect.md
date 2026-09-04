<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-153031 -->
<!-- 功能名称: sls-config-source -->
<!-- 阶段: review -->
<!-- 前置文档: docs/04_testing/unit-tests/B20260904-153031-sls-config-source-test-plan.md -->
<!-- 创建时间: 2026-09-04T15:30:31+08:00 -->
<!-- 关系: extends=B20260904-152149; relates_to=F20260902-101243 -->

# SLS 配置来源缺陷记录

## 根因分析

前次修复只移除了 SLS project、region、endpoint 的环境变量回退，`get_credentials` 仍通过 Keychain 和环境变量获取 AK/SK，未满足 SLS 全部配置位于私有配置文件的要求。

## 修复方案

- 将 `access_key`、`access_secret` 纳入每个 profile 的 `sls` 配置。
- 查询和就绪检查共享同一已加载的配置，不再读取 SLS Keychain 或环境变量。
- 配置模板、README、Skill 契约和设计说明同步为该来源边界。

## 回归测试与验证

- 红灯：新增两项测试在旧接口上报错，并证明旧实现仍支持环境变量凭据。
- 绿灯：两项测试通过。
- 全量：`python3 scripts/test_service_ops.py` 通过，130 tests / 0 failures。
