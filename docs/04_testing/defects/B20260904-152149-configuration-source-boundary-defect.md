<!-- PDLC-TRACE -->
<!-- 功能ID: B20260904-152149 -->
<!-- 功能名称: configuration-source-boundary -->
<!-- 阶段: review -->
<!-- 前置文档: docs/04_testing/unit-tests/B20260904-152149-configuration-source-boundary-test-plan.md -->
<!-- 创建时间: 2026-09-04T15:21:49+08:00 -->
<!-- 关系: extends=B20260904-145318; relates_to=F20260902-101243 -->

# 非敏感配置来源边界缺陷记录

## 根因分析

共享 profile 状态从 `SERVICE_OPS_PROFILE` 读取，SLS 连接解析又将 project、region、endpoint 回退到环境变量。这让非敏感运行配置存在私有配置文件之外的第二来源，与配置边界不一致。

## 影响范围

- 父进程环境可意外改变脚本未显式指定时选用的 profile。
- SLS 路由可绕过 `~/.service-ops/config.yaml` 的已审核配置。
- README、Skill 和 `setup.py --help` 误导用户继续使用该环境变量。

## 修复方案

- 将活跃 profile 保持为进程内状态：每次脚本入口未传 `--profile` 时固定回到 `default`。
- 删除 SLS project、region、endpoint 的环境变量回退；仍允许命令行显式覆盖私有配置。
- 保留 Keychain 和环境变量作为 Cookie、AK/SK、测试库密码的凭据来源。
- 同步更新用户文档、Skill 契约、设计记录和 setup 帮助。

## 回归测试与验证

- 红灯：两个新增测试在旧实现中失败，分别证明 profile 和 SLS 路由可被环境变量改变。
- 绿灯：两个新增测试通过。
- 全量：`python3 scripts/test_service_ops.py` 通过，129 tests / 0 failures。
- 静态：`python3 -m py_compile scripts/*.py` 与 `git diff --check` 通过。
