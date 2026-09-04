<!-- PDLC-TRACE -->
<!-- 功能ID: B20260903-110033 -->
<!-- 功能名称: service-ops-boundary-safety -->
<!-- 阶段: review -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-03T11:00:33+08:00 -->
<!-- 关系: resolves=F20260902-101243; extends=F20260903-100325 -->

# service-ops 边界安全缺陷记录

## 根因分析

工单预检把任意 `WHERE` 当作 DML 限定条件，子查询可绕过目标表限制；SQL 拆分未识别注释。新增 SLS dry-run 重复构造查询，导出与共享查询行数不一致，工单网络错误会冒泡。评测器未验证 case ID，profile 的 PaaS 环境变量也没有隔离。

## 修复方案

- 仅接受 `UPDATE`/`DELETE` 的顶层 `WHERE`，并在语句拆分时跳过引号、行注释和块注释中的分号。
- 将 PaaS 请求行数设为调用方参数；导出传递已经验证的 SQL LIMIT。
- 为工单提交及动作调用输出受控网络错误和已完成 ID；dry-run 用原始参数构造计划。
- 限制 SLS 单次查询为 1000 行；真实宽范围查询要求显式 `--allow-wide-range`。
- 隔离非 default profile 的环境变量，移除公开模板与文档中的部署别名；评测器拒绝重复 case 并支持行为场景。

## 回归测试

- 红灯：11 项新回归测试覆盖嵌套 WHERE、注释分号、网络失败、行数传递、profile 凭据、dry-run 输入、SLS 边界和评测契约，均在修复前失败。
- 绿灯：全量 Python 单元测试 91 项通过。
- 附加验证：Python 编译、Shell 语法、JSON/Skill 结构和无部署别名扫描通过；未调用外部系统。
