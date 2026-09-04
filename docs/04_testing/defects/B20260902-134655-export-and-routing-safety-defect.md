<!-- PDLC-TRACE -->
<!-- 功能ID: B20260902-134655 -->
<!-- 功能名称: export-and-routing-safety -->
<!-- 阶段: review -->
<!-- 前置文档: docs/02_design/architecture/F20260902-101243-service-ops-governance-arch.md -->
<!-- 创建时间: 2026-09-02T13:46:55+08:00 -->
<!-- 关系: relates_to=F20260902-101243 -->

# 导出与路由安全缺陷

## 根因

Excel 导出将数据库字符串原样写入单元格，可能被办公软件当作公式执行。工单预检在异常处理完成后才构造工单，配置缺失会抛出 traceback。配置的 profile 名称与 SLS 环境变量命名规则分离，且 SLS offset 查询仍返回 page 续取指针。

## 影响范围

- 用户打开含不可信字段值的 XLSX 文件时的公式注入风险。
- 工单配置不完整时的可读错误与预检可用性。
- 自定义 profile 的配置、Keychain 与环境变量使用一致性。
- SLS offset 分页客户端的后续取数位置。

## 修复方案

- 对 Excel 标题和数据中以 `= + - @` 开头的字符串增加文本前缀。
- 把工单构造移入现有预检错误处理范围。
- 在共享配置模块统一校验 profile 名称，SLS 重用该规则。
- 截断元数据在 offset 模式返回 `next_offset`，page 模式仍返回 `next_page`。

## 回归测试

`scripts/test_service_ops.py` 覆盖公式文本单元格、工单预检配置错误、无效 profile 的受控 CLI 错误、自定义 profile 校验及 offset 续取指针。完整套件 56 项通过。
