<!-- PDLC-TRACE -->
<!-- 功能ID: B20260903-112611 -->
<!-- 功能名称: trace-guidance-and-setup -->
<!-- 阶段: review -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-03T11:26:11+08:00 -->
<!-- 关系: resolves=F20260902-101243; extends=B20260903-111241 -->

# TraceId 引导与能力初始化缺陷记录

## 根因分析

TraceId 采集器丢弃子查询的 stderr，因此超过一小时的范围拒绝被统一改写为权限 doctor 建议。安装脚本又固定检查全量依赖，忽略了已有能力分级检查，导致仅使用 SLS 的用户也会被无关依赖阻塞。

## 修复方案

- 仅识别稳定的宽范围拒绝标志，并返回安全下一步：先 dry-run，再显式确认范围；其余失败仍保持 doctor 引导。
- 为安装脚本增加受限且本地校验的 `--capability` 参数，直接委托既有 `setup.py` 能力校验；不新增依赖、不改变默认全量行为，也不自动安装。

## 回归测试

- 红灯：宽范围 stderr 必须包含 `--allow-wide-range` 且不得建议 doctor；安装脚本必须把选择的 capability 传给 setup，并在调用依赖检查前拒绝未知 capability。
- 绿灯：全量 Python 单元测试、Python 编译、Shell 语法和 diff 空白检查通过。
- 未调用 SLS、PaaS、数据库或工单外部接口。
