# service-ops

面向已配置服务的受控运维 Skill：SLS 日志与 TraceId 排障、只读数据库验证、Excel 导出和 PaaS 变更工单。真实 SLS 查询支持 macOS/Unix 主线程；私有配置和凭据不得提交。

## 快速开始

```bash
python3 -m pip install -r requirements.lock
python3 scripts/setup.py --init
# 填写 ~/.service-ops/config.yaml（不填写凭据）
python3 scripts/setup.py --check --capability sls
```

`requirements.lock` 是日常安装与 CI 的完整锁定集，已在 Python 3.14/macOS 隔离环境验证。按需检查 `sls`、`paas`、`db`、`export`、`apply` 或全部能力 `all`。

## 配置与凭据

`setup.py --init` 会从 [配置模板](config/settings.yaml.example) 创建权限为 `600` 的 `~/.service-ops/config.yaml`。填写 SLS 的 project/region/endpoint/AK/SK、服务的生产 group 与测试库、PaaS 契约和可选脱敏规则；PaaS 查询成功响应固定为 `[{"columnList": [...], "rows": [...]}]`。

SLS 配置（含 AK/SK）只从该私有文件读取。PaaS Cookie 与测试库密码不写配置文件：默认 profile 使用 Keychain 或 `PAAS_COOKIE`、`TEST_DB_PASSWORD`；其他 profile 使用 `_<PROFILE>` 环境变量后缀。

## 常用场景

示例中的服务、TraceId 和路径均为占位符，必须替换为用户明确提供、已配置的值。

### 查询日志

```bash
python3 scripts/sls_query.py --doctor --service orders --profile default
python3 scripts/sls_query.py --service orders --level ERROR --from 15m --limit 100
python3 scripts/sls_query.py --dry-run --service orders --query 'TraceId: abc-123' --from 1h
```

默认时间范围是 15 分钟；真实查询超过一小时必须先 dry-run，再附加 `--allow-wide-range`。需要 JSONL 时使用 `--jsonl`，单次最多 1000 行。

### TraceId 排障

```bash
tmp_dir="$(mktemp -d)" && chmod 700 "$tmp_dir"
python3 scripts/sls_log_fetcher.py --trace-id abc-123 --service orders --profile default --from 15m > "$tmp_dir/logs.json"
python3 scripts/log_analyzer.py < "$tmp_dir/logs.json" > "$tmp_dir/analysis.json"
```

`truncated_services` 非空代表证据不完整；采集失败不能解释为无日志。阅读后删除该临时目录。

### 数据验证与 Excel 导出

只接受明确服务、环境、用途和 SQL。验证查询必须是显式字段、无副作用的单条 `SELECT`，且 `LIMIT` 不超过 100：

```bash
python3 scripts/db_query.py --env test --service orders \
  --purpose '核对订单状态' --sql 'SELECT id, status FROM orders WHERE id = 42 LIMIT 1'
```

导出上限为 10000 行，目标必须是绝对 `.xlsx` 路径：

```bash
python3 scripts/db_export.py --env prod --service orders \
  --purpose '用户已授权的订单核对' --sql-file /absolute/path/orders.sql \
  --output /absolute/path/orders.xlsx
```

生产导出须在当前请求获得明确授权；已有文件仅在传入 `--overwrite` 后覆盖。

### 工单预检与提交

工单不会自动触发，只能在用户显式调用 `$skills-service-ops` 并明确要求该操作时执行。

```bash
python3 scripts/db_apply.py --env prod --service orders \
  --reason '修复订单状态' --sql-file /absolute/path/change.sql
python3 scripts/db_apply.py --env prod --service orders \
  --reason '修复订单状态' --sql-file /absolute/path/change.sql \
  --submit --confirm '<confirmation_token>'
```

先核对预检输出的 SQL、group、窗口和 token；`UPDATE`/`DELETE` 必须有顶层 `WHERE`，`DROP`/`TRUNCATE` 还需 `--allow-destructive`。token 一次性消费，失败时先核对工单，不能重放。

### 使用 profile

默认使用 `default`。其他部署显式使用 `--profile regional`；profile 只能由字母、数字、`-`、`_` 构成并以字母开头。服务、SLS 路由和 PaaS 契约只从私有配置文件读取；环境变量仅用于运行时凭据。

## 常见问题

**依赖或配置失败？** 运行 `python3 scripts/setup.py --check --capability <能力>`，按错误补齐私有配置或 Keychain/环境变量。

**SLS 超时、权限失败或结果截断？** 先运行 `--doctor`，缩小范围；截断数据只能视为不完整证据。

**PaaS 返回结构无效？** 当前只支持上述固定响应包络；核对私有契约，勿将内部字段写入仓库。

更多 Agent 路由与安全规则见 [SKILL.md](SKILL.md)、[SLS 分析计划](references/sls-analysis.md) 和 [行为评测说明](references/evaluation.md)。
