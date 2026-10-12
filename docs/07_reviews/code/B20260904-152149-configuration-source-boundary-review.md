<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-152149 -->
<!-- 功能名称: configuration-source-boundary -->
<!-- 阶段: review -->
<!-- 前置文档: docs/04_testing/defects/B20260904-152149-configuration-source-boundary-defect.md -->
<!-- 创建时间: 2026-09-04T15:21:49+08:00 -->
<!-- 关系: extends=B20260904-145318; relates_to=F20260902-101243 -->

# 非敏感配置来源复核

## 验收项

- 非敏感运行配置只从 `~/.service-ops/config.yaml` 和显式 CLI 参数读取。
- 未传 `--profile` 时始终使用 `default`。
- Keychain 与环境变量只保留为运行时凭据来源。

## 结果

通过。生产代码中已不存在 `SERVICE_OPS_PROFILE` 或 SLS project/region/endpoint 的环境变量读取；回归测试和缺陷记录保留这些名称以验证旧行为被拒绝。SLS 凭据与 PaaS、测试库凭据的环境变量回退仍保留，未改变安全边界。

## 验证

- 回归测试：2 passed。
- 全量测试：129 passed。
- 编译与 diff 格式检查：通过。
