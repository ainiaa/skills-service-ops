<!-- PDLC-TRACE -->
<!-- 功能ID: B20260902-184556 -->
<!-- 功能名称: profile-readiness -->
<!-- 阶段: review -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-02T18:45:56+08:00 -->
<!-- 关系: resolves=F20260902-101243 -->

# profile-readiness 缺陷记录

## 根因分析

`setup.py --check --profile <profile>` 使用指定 profile 加载配置，但 PaaS Cookie 读取仍依赖当前活动 profile。因此不同 profile 的 Keychain 凭据可能被错误地判定为就绪或未配置。数据库就绪检查只校验共享测试库连接，不能在调用前发现指定服务漏配 `test_database`。

## 影响范围

- `setup.py --check --capability paas|export|apply --profile <profile>` 的 Keychain 就绪结论。
- 使用测试库前的 `setup.py --check --capability db` 配置反馈。

## 修复方案

- 共享 Keychain 读取与 `get_cookie` 接受可选 profile，`setup.py` 将其已解析的 profile 显式传入。
- `setup.py` 增加 `--service`，在 `db` 或 `all` 检查时同时校验该服务的 `test_database` 映射。
- 增加 8 个行为评测场景，覆盖日志、TraceId、模糊数据库请求、生产导出、显式工单、证据截断与敏感输出边界。

## 回归测试

- 红灯：3 项新增回归测试分别暴露 Cookie profile、就绪检查 profile 传递和服务测试库映射问题。
- 绿灯：全量 72 项 Python 单元测试通过。
- 附加验证：Python 编译、`install.sh` Shell 语法、行为评测 JSON 与 Skill 结构校验均通过。
