<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-153031 -->
<!-- 功能名称: sls-config-source -->
<!-- 阶段: review -->
<!-- 前置文档: docs/04_testing/defects/B20260904-153031-sls-config-source-defect.md -->
<!-- 创建时间: 2026-09-04T15:30:31+08:00 -->
<!-- 关系: extends=B20260904-152149; relates_to=F20260902-101243 -->

# SLS 配置来源复核

## 验收

- SLS project、region/endpoint、AK、SK 只从私有配置读取。
- `setup.py --check --capability sls` 与真实 SLS 查询使用同一配置来源。
- 生产代码不存在 `SLS_LOG_AK`、`SLS_LOG_SK`、`sls-ak` 或 `sls-sk` 的读取入口。

## 结果

通过。仅 PaaS Cookie 与测试库密码保留 Keychain/环境变量凭据回退；SLS 配置文件由 `setup.py --init` 创建并限制为 `600` 权限。

## 验证

- 回归测试：2 passed。
- 全量测试：130 passed。
- 脚本编译和 diff 格式检查：通过。
