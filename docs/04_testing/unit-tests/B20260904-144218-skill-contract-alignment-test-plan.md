<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-144218 -->
<!-- 功能名称: skill-contract-alignment -->
<!-- 阶段: 测试 -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-04T14:42:18+08:00 -->
<!-- 关系: extends=B20260904-140530; relates_to=F20260902-101243 -->

# Skill 契约一致性测试计划

| 场景 | 类型 | 断言 |
|---|---|---|
| 缺少用途 | 异常 | `db_query.py` 和 `db_export.py` 都拒绝未传 `--purpose` 的调用。 |
| 配置模板 | 正常/引导 | 模板明确由 `setup.py --init` 写入 `~/.service-ops/config.yaml`。 |
| 干净安装 CI | 可复现性 | 工作流从 `requirements.lock` 安装，并运行全量依赖就绪检查。 |

TDD 记录：先新增回归测试；旧实现未拒绝缺少用途、模板文案错误且不存在 CI 工作流，测试红灯。最小实现后绿灯。
