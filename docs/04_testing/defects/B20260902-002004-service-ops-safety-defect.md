<!-- PDLC-TRACE -->
<!-- 功能ID: B20260902-002004 -->
<!-- 功能名称: service-ops-safety -->
<!-- 阶段: review -->
<!-- 前置文档: 无 -->
<!-- 创建时间: 2026-09-02T00:20:04+08:00 -->

# service-ops 安全边界与路由缺陷

## 根因

Skill 指令与脚本参数契约未同步；只读查询和导出只检查 SQL 类型，变更工单只检查首个关键字。因此无 TraceId 的普通日志请求会被路由到不支持的命令，宽查询、超额导出和无条件 DML 可穿过脚本级校验。

## 影响范围

- `SKILL.md` 的发现与路由规则。
- 数据库验证、Excel 导出、PaaS DDL/DML 工单脚本。
- 首次初始化说明与健康检查退出状态。

## 修复方案

- 使 skill 描述和路由仅声明真实支持的 TraceId 排障，并声明已支持的工单操作。
- 排障查询要求显式列和最多 100 行的 `LIMIT`；导出要求绝对 XLSX 路径和最多 10000 行的 `LIMIT`。
- 拒绝无 `WHERE` 的 `UPDATE`/`DELETE`；`DROP`/`TRUNCATE` 需 `--allow-destructive`，且仍走原有预检与确认 token。
- README 改为使用私有配置初始化；`--check` 对不完整状态返回失败。

## 回归测试

`scripts/test_service_ops.py` 覆盖宽查询、超额导出、相对导出路径、无条件 DML、危险 DDL 显式授权及缺失配置/凭据。完整套件为 17 项通过。
