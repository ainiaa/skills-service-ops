<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-145318 -->
<!-- 功能名称: ci-portability -->
<!-- 阶段: review -->
<!-- 前置文档: docs/04_testing/defects/B20260904-144218-skill-contract-alignment-defect.md -->
<!-- 创建时间: 2026-09-04T14:53:18+08:00 -->
<!-- 关系: extends=B20260904-144218; relates_to=F20260902-101243 -->

# Unix CI 覆盖与 Action 引用漂移缺陷记录

## 根因分析

Skill 声明支持 macOS/Unix，但工作流只在 macOS 运行；同时 `actions/checkout@v4` 与 `actions/setup-python@v5` 是可变标签，未来可指向不同实现。

## 影响范围

- Linux 的环境变量凭据回退和 Unix 信号 deadline 路径没有持续验证。
- 构建依赖的第三方 Action 可能在仓库未改动时发生漂移。

## 修复方案

- 将验证工作流扩展为 macOS 与 Ubuntu 运行器矩阵。
- 使用 `git ls-remote` 核对后，将 checkout 固定到 v4.2.2 commit、setup-python 固定到 v5.6.0 commit。

## 回归测试与验证

- 红灯：新增工作流契约测试无法找到 Unix 矩阵与完整 commit SHA。
- 绿灯：目标测试及全量 126 项测试通过，脚本编译通过。
- 工作流 YAML 仅做本地语法与结构验证；远程 GitHub runner 结果仍需首次推送后观察。
