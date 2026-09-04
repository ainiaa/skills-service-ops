<!-- PDLC-TRACE -->
<!-- 功能ID: B20260902-144721 -->
<!-- 功能名称: configuration-output-safety -->
<!-- 阶段: review -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-02T14:47:21+08:00 -->
<!-- 关系: relates_to=F20260902-101243 -->

# 配置、导出与就绪检查缺陷

## 根因

测试库直连未校验服务是否指定 `test_database`，PaaS 查询假定首项为对象，Excel 文件系统错误未被 CLI 受控处理。就绪检查只覆盖 `paas` 与 `sls`，无法在实际使用前检查测试库、导出和 DDL/DML 工单契约。文档将生产导出描述为二次确认，但产品决策是当前请求的明确授权和直接命令为单次确认。

## 修复方案

- 拒绝没有 `test_database` 的测试库连接，并在 `db` 就绪检查中验证测试库 host 与 user；文档要求数据库账号仅拥有该目标库的最小权限。
- 对无效 YAML、非对象配置根节点、无效 PaaS 成功响应及 Excel 落盘失败返回受控错误。
- 扩展 `setup.py --capability` 为 `db`、`export`、`apply`，`all` 覆盖所有已声明能力。
- 用 `--jsonl` 表达结构化日志输出，保留 `--analysis` 兼容别名；生产导出不新增 token。

## 回归测试

`scripts/test_service_ops.py` 覆盖测试库目标库缺失、无效 YAML、无效 PaaS 响应、Excel 写入失败、按能力就绪检查、缺少 YAML 解析器及 JSONL 兼容别名。完整套件 64 项通过。
