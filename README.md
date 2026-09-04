# service-ops

统一服务运维 Skill：SLS TraceId 排障、受控 SQL 导出和受控 PaaS 变更工单提交。

## 初始化

```bash
python3 -m pip install -r requirements.lock
python3 scripts/setup.py --init
# 编辑 ~/.service-ops/config.yaml 后
python3 scripts/setup.py --check --capability sls
```

`requirements.txt` 保留顶层依赖意图；日常安装和 CI 使用已在 Python 3.14/macOS 隔离环境解析并验证的 `requirements.lock`。

只使用 SLS 时检查 `sls`；生产查询检查 `paas`，测试库验证检查 `db`，导出检查 `export`，工单检查 `apply`；全部能力均需使用时才检查 `all`。已有依赖和配置时，可用 `./install.sh --capability sls` 仅检查某项能力的依赖与配置初始化状态。

填写 `sls.project`、`sls.region`（或 `sls.endpoint`）、`services.<service>.prod_db_group` 与 `services.<service>.test_database`。测试库账号必须只拥有对应 `test_database` 的最小权限。PaaS 的 Cookie 前缀、静态请求头、查询/提交/工单端点及字段映射，和日志服务/实体识别正则也只填写在私有配置中；查询成功响应固定为 `[{"columnList": [...], "rows": [...]}]`，其他结构暂不支持。凭据不得写入文件：default profile 使用 Keychain 的 `paas-cookie` 或 `PAAS_COOKIE`；其他 profile 使用 `paas-cookie` 或 `PAAS_COOKIE_<PROFILE>`。SLS 使用 Keychain 的 `sls-ak`、`sls-sk` 或 `SLS_LOG_AK`、`SLS_LOG_SK`；测试库密码使用 Keychain 的 `test-db-password` 或同 profile 的 `TEST_DB_PASSWORD`。Keychain 读取最多等待 10 秒，失败后会回退到同一 profile 的环境变量。SLS 依赖锁定在已验证的 0.9.x。首次使用 SLS 前运行 `python3 scripts/sls_query.py --doctor --service <service-or-logstore>`；它会做一次最近 5 分钟、最多 1 条且不输出日志内容的只读权限探针。

支持 macOS 与 Unix 主线程运行真实 SLS 查询；Windows 不在支持范围内。

已有私有配置需要补充 `paas.cookie_prefix`、`paas.request_headers`、`paas.query_contract`、`paas.apply_*`、`paas.task_*` 以及 `log_analysis` 下的识别与 `redaction_patterns` 脱敏正则。它们属于内部部署契约，只能保留在 `~/.service-ops/config.yaml`，不得提交到仓库。

`db_export.py` 只导出带不超过 10000 行数值 `LIMIT` 的单条无副作用 `SELECT` 到绝对路径的 XLSX 文件，并转义可能被 Excel 解释为公式的文本；带反引号的危险函数、`LAST_INSERT_ID`、`INTO @var` 和 `@var :=` 也会被拒绝。`--sql`（含 `-` 标准输入）与 `--sql-file` 必须二选一，文件不可读取时会返回受控错误。生产导出须在当前请求中明确授权；直接执行导出命令即为调用者确认，不使用额外 token。排障查询必须使用显式字段和不超过 100 行的 `LIMIT`；测试库连接、鉴权和执行失败会返回受控错误。`db_apply.py` 对 DDL/DML 和 approve/execute/recall 均先预检，并以用户私有目录下权限为 `600` 的计划记录绑定随机确认指纹、resolved profile、PaaS 提交目标与精确请求体；只有完全一致、尚未消费的预检计划才会执行。修改 SQL、服务、profile、目标、原因、`--batch-size` 或 action 参数必须重新预检。确认时先验证 Cookie，再消费 token，落盘记录立即缩减为消费时间戳；请求失败时先核对 PaaS 工单，不得盲目重试。标记保留七天后会在后续预检时清理。`UPDATE`/`DELETE` 必须带 `WHERE`，`DROP`/`TRUNCATE` 还需 `--allow-destructive`。`setup.py --check --capability <all|paas|sls|db|export|apply>` 会检查对应配置、凭据和运行依赖；检查测试库时可附加 `--service <service>`，提前验证该服务的 `test_database` 映射和密码。缺失时返回非零退出码。

关键词、级别、TraceId、分页、原始 JSON、`doctor` 与无凭据/API 调用的 `--dry-run` 查询计划均由内置 `scripts/sls_query.py` 提供；普通日志和 TraceId 查询未指定时间时默认最近 15 分钟，真实查询超过 1 小时须先 dry-run，再显式传 `--allow-wide-range`；单次查询最多 1000 行。趋势、Top-N、分组、分位数或分布需求先 dry-run 生成查询计划，确认范围后再执行。TraceId 根因排障使用 `scripts/sls_log_fetcher.py` 收集证据，再由 `log_analyzer.py` 生成根因线索。

PaaS DDL/DML 工单不会由 Skill 自动触发。只有用户明确调用 `$skills-service-ops`，并清楚说明要提交、审批、立即执行或撤回工单时，才允许使用 `db_apply.py`；即使 Skill 已因日志排障被加载，也不能据此执行工单操作。
