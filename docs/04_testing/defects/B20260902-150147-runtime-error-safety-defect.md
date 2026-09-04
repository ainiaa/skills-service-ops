<!-- PDLC-TRACE -->
<!-- 功能ID: B20260902-150147 -->
<!-- 功能名称: runtime-error-safety -->
<!-- 阶段: review -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-02T15:01:47+08:00 -->
<!-- 关系: relates_to=F20260902-101243 -->

# 运行时错误与 SLS 读权限缺陷

## 根因

Excel 导出在参数校验后、受控错误边界外读取 SQL 文件，且允许同时传入内联 SQL 和文件。测试库查询只捕获通用本地异常，未转换 PyMySQL 的数据库错误。SLS doctor 仅验证 Logstore 与索引元数据，不能证明实际 `GetLogs` 权限可用。

## 修复方案

- `db_export.py` 将 SQL 来源定义为互斥必选参数，并将文件读取和编码错误转换为参数错误。
- `db_query.py` 将 PyMySQL 连接、鉴权和查询错误转换为不含敏感细节的受控错误。
- `sls_query.py --doctor` 在元数据检查后执行最近 5 分钟、最多 1 条且不输出日志内容的 `get_logs` 探针，并返回行数和耗时。
- Skill 统一汇报执行范围、确认结论、证据局限和下一步，防止把未执行路径表述为已确认事实。

## 回归测试

`scripts/test_service_ops.py` 覆盖 SQL 来源冲突、不可读取 SQL 文件、PyMySQL 异常和 doctor 的单条读权限探针。完整套件 68 项通过；未执行真实 SLS、PaaS 或数据库访问。
