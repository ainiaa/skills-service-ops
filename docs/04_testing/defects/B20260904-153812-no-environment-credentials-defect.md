<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-153812 -->
<!-- 功能名称: no-environment-credentials -->
<!-- 阶段: review -->
<!-- 前置文档: docs/04_testing/unit-tests/B20260904-153812-no-environment-credentials-test-plan.md -->
<!-- 创建时间: 2026-09-04T15:38:12+08:00 -->
<!-- 关系: extends=B20260904-153031; relates_to=F20260902-101243 -->

# 环境变量凭据读取缺陷记录

## 根因分析

PaaS Cookie 与测试库密码仍在 Keychain 未命中时读取 `PAAS_COOKIE`、`TEST_DB_PASSWORD` 环境变量，违反所有配置和凭据不从环境变量获取的约束。

## 修复方案

- 配置模板新增 `paas.cookie` 与 `test_db.password`。
- Cookie、测试库密码、SLS AK/SK 均使用 Keychain 优先、对应 profile 私有配置文件兜底。
- 删除生产代码的环境变量读取和 profile 环境变量命名辅助函数。
- 更新 README、Skill 契约、设计记录和错误提示。

## 回归测试与验证

- 红灯：两项 PaaS/测试库配置兜底测试在旧接口上报错。
- 绿灯：三项凭据来源测试通过。
- 全量：`python3 scripts/test_service_ops.py` 通过，131 tests / 0 failures。
