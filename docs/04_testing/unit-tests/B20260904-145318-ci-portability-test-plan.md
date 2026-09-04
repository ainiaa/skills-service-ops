<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-145318 -->
<!-- 功能名称: ci-portability -->
<!-- 阶段: 测试 -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-04T14:53:18+08:00 -->
<!-- 关系: extends=B20260904-144218; relates_to=F20260902-101243 -->

# CI 可移植性测试计划

| 场景 | 类型 | 断言 |
|---|---|---|
| Unix 运行器矩阵 | 可移植性 | 工作流包含 macOS 和 Ubuntu，并使用矩阵选择运行器。 |
| Action 供应链 | 安全 | checkout 与 setup-python 使用经核对的完整 commit SHA。 |
| 干净安装 | 正常 | 每个矩阵任务从 `requirements.lock` 安装并运行依赖检查。 |

TDD 记录：先添加工作流静态契约测试；旧工作流仅包含 macOS 且使用可变版本标签，测试红灯。最小工作流修改后绿灯。
