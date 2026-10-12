<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-140530 -->
<!-- 功能名称: dependency-lock -->
<!-- 阶段: review -->
<!-- 前置文档: docs/04_testing/defects/B20260904-134917-sls-hard-deadline-defect.md -->
<!-- 创建时间: 2026-09-04T14:05:30+08:00 -->
<!-- 关系: extends=B20260904-134917; relates_to=F20260902-101243 -->

# 运行依赖不可复现缺陷记录

## 根因分析

`requirements.txt` 只声明顶层依赖，除 SLS SDK 外未固定版本，也没有记录传递依赖；不同安装时刻可能解析到不同运行集，无法稳定复现就绪检查和测试环境。

## 影响范围

- 新环境安装可能因传递依赖变动出现不同的运行行为。
- 依赖缺失提示无法给出可复现的安装目标。

## 修复方案

- 基于 Python 3.14/macOS 的隔离安装解析结果新增完整 `requirements.lock`。
- README、Skill 和 `install.sh` 的安装指引统一使用锁定集；`requirements.txt` 保留顶层依赖意图。

## 回归测试与验证

- 红灯：缺少 lock 文件时，依赖锁定回归测试失败。
- 绿灯：lock 固定全部直接与传递运行依赖；在隔离环境中 `setup.py --check-dependencies --capability all` 通过。
- 全量验证：隔离环境 `python3 scripts/test_service_ops.py`（123 通过）、脚本编译及 SLS dry-run。
- 真实 PaaS/SLS 集成和外部 Agent JSONL 评测仍需授权私有环境；本次未发起真实网络请求。
