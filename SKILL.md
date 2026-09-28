---
name: skills-service-ops
description: 对已配置服务执行 SLS 日志检索、TraceId 排障、趋势或 Top-N 查询计划及受控数据库验证或 Excel 导出；不用于通用文件导出或未指定服务的数据库操作。
---

# service-ops

统一处理服务排障、SLS 日志检索、数据库验证、Excel 导出与变更工单；全部能力均由本项目提供。

下文的 `<skill-dir>` 指本文件所在目录的绝对路径。

## 快速输入

信息不全时，只追问当前意图所需字段，不要猜测：

| 意图 | 请用户提供 |
|---|---|
| 查日志 | 服务或 Logstore；未指定时间时默认最近 15 分钟，未指定 profile 时默认 `default`；关键词、级别和 TraceId 均可选，不提供则查所有日志 |
| TraceId 排障 | TraceId、服务或 Logstore、环境；未给时间时默认最近 15 分钟 |
| 数据验证 | 服务、环境、用途、单条带 LIMIT 的 SELECT |
| Excel 导出 | 服务、环境、用途、完整 SQL、绝对输出路径；生产还需当前请求明确授权 |
| 工单 | 用户在当前请求显式调用 `$skills-service-ops`，并提供服务、环境、变更原因和完整 SQL |

## 路由

| 请求 | 处理方式 |
|---|---|
| 关键词、级别、时间范围或分页日志检索 | 使用 `scripts/sls_query.py`。 |
| 基于 TraceId 的根因排查 | 用 `scripts/sls_log_fetcher.py` 收集证据，再用 `scripts/log_analyzer.py` 分析。 |
| 错误趋势、Top-N、分组、分位数或分布分析 | 先阅读 [SLS 分析查询计划](references/sls-analysis.md)，用 `--dry-run` 仅生成计划；获得范围确认后才执行。 |
| 排障时小范围数据验证 | 使用 `scripts/db_query.py`；生产走 PaaS，测试走直连 MySQL。 |
| 按已配置服务导出查询结果 | 使用 `scripts/db_export.py` 输出 Excel。 |
| 为已配置服务提交 DDL/DML 工单或操作已知工单 | 仅当用户显式调用 `$skills-service-ops` 且明确要求工单操作时，使用 `scripts/db_apply.py`。 |

## 共同边界

1. 数据库验证、导出和变更所需的服务、环境、用途和 SQL 必须由用户明确提供；不得猜测服务、group 或环境。日志检索仅可在当前目录唯一服务映射或显式参数可确定范围时执行，并在结果中说明最终服务与环境。
2. SLS、PaaS 与测试库的全部配置和凭据均只从权限为 `600` 的私有配置文件或 macOS Keychain（service=`service-ops`）读取；Keychain 中同 profile 的 `sls-ak`、`sls-sk`、`paas-cookie`、`test-db-password` 优先，配置文件兜底。Keychain 读取最多等待 10 秒，错误或超时后回退到同一 profile 的配置文件。禁止写入源码、命令行参数、环境变量或对话输出。
3. 生产查询、生产导出和任何变更工单都必须先得到用户明确授权。输出不得包含 Cookie、授权头或完整导出数据。SLS 日志默认原样输出；仅当用户明确要求脱敏时，才对日志和分析摘要使用 `--redact`。
4. PaaS 失败属于证据或提交失败，不能当作空结果或成功；只报告可确认的结果。
5. 工单操作不得由 Skill 的自动匹配、排障上下文或“处理一下”之类的隐含表达触发；必须由用户在当前请求中显式调用 `$skills-service-ops` 并说明提交、审批、立即执行或撤回的具体意图。

## 结果呈现

每次执行后按以下顺序简要汇报：已执行的服务/环境/时间范围与命令路径、已确认发现或导出行数、证据局限（采集失败、截断、权限或范围不足）以及下一步。不得把未执行的查询当作证据；SLS 日志是否脱敏遵从用户明确要求，不展示完整导出数据。

## 排障

先按用户指定的配置 profile 收集 TraceId 日志：

```bash
TMP_DIR="$(mktemp -d)"
chmod 700 "$TMP_DIR"
python3 <skill-dir>/scripts/sls_log_fetcher.py \
  --trace-id "<trace-id>" --service "<service-or-logstore>" --profile "<profile>" \
  --from "<15m|1h|epoch>" \
  > "$TMP_DIR/logs.json"
python3 <skill-dir>/scripts/log_analyzer.py < "$TMP_DIR/logs.json" > "$TMP_DIR/analysis.json"
# 读取并报告分析结果后，删除由 mktemp 创建的临时目录：rm -rf -- "$TMP_DIR"
```

首次使用或出现采集失败时，先运行 `python3 <skill-dir>/scripts/sls_query.py --doctor --service "<service-or-logstore>" --profile "<profile>"` 排查权限、路由和索引。doctor 会额外执行最近 5 分钟、最多 1 条且不输出日志内容的只读探针，确认实际日志读取权限。使用 `--level` 时必须有 `level` 或 `content.level` 字段索引，否则真实查询会拒绝执行；不得把级别条件退化为全文搜索。dry-run 不读取远端索引，带 `--level` 的计划标记为索引未验证，执行前用 doctor 核实。SLS SDK 单次请求限制为 30 秒；macOS/Unix 主线程的整次 SLS 查询以进程级 60 秒定时器中断，TraceId 采集子进程也限制为 60 秒。不支持该定时器的平台会拒绝真实查询而不提供虚假的时限承诺。普通日志与 TraceId 查询未指定时间时默认最近 15 分钟、最新日志优先；需要较早日志优先时显式传 `--forward`。真实查询超过 1 小时须先用 `sls_query.py --dry-run` 确认范围，再显式传 `--allow-wide-range`。任一服务 `status: error` 时，报告证据采集失败，不得把它解释成无日志；`truncated: true` 时，说明结果可能不完整。只有日志形成具体数据假设后，才执行一条经过确认的非锁定 `SELECT`；查询必须使用显式字段并带不超过 100 行的数值 `LIMIT`。

采集结果会携带已解析的配置 profile，分析器自动使用同一 profile；手工输入标准 JSON 时可显式传 `--profile <profile>`。默认保留原始 SLS 日志；只有用户明确要求脱敏时，才在 `sls_query.py`、`sls_log_fetcher.py` 和 `log_analyzer.py` 命令上附加 `--redact`。最终报告区分“已确认”“待验证”“证据不完整”和“证据采集失败”，并只摘要必要证据；分析摘要中的 `truncated_services` 非空时，必须标记为“证据不完整”。若识别到 `related_services`，先向用户列出候选服务并获得确认，再使用 `sls_log_fetcher.py --related-services <service...>` 扩展采集，不得自动跨服务抓取。数据库验证仅允许单条无副作用 SELECT，且拒绝带反引号的 `GET_LOCK`、`RELEASE_LOCK`、`SLEEP`、`BENCHMARK`、`LOAD_FILE`、`LAST_INSERT_ID` 等函数，以及 `INTO @var`、`@var :=` 等会改变锁、连接状态、资源或读取服务端文件的形式。

## 导出

仅接受包含不超过 10000 行数值 `LIMIT` 的单条非锁定 `SELECT`，输出为 Excel。`--sql`（可传 `-` 读取标准输入）与 `--sql-file` 二选一；执行前要求服务、环境、用途、完整 SQL 和绝对输出路径。生产导出必须在当前请求中得到用户明确授权；直接执行命令即视为调用者已确认，不增加二次确认 token。

```bash
python3 <skill-dir>/scripts/db_export.py \
  --env "<prod|test>" --service "<service>" \
  --purpose "<export purpose>" \
  --sql-file "<sql-file>" --output "<absolute-output>.xlsx"
```

已有文件不会被覆盖；只有在用户确认覆盖时，才增加 `--overwrite`。只报告导出路径和行数，不在对话中展示数据行。

## Apply

仅接受 DDL/DML。`UPDATE` 与 `DELETE` 必须包含 `WHERE`；`DROP` 与 `TRUNCATE` 必须显式附加 `--allow-destructive`。先要求完整 SQL、服务、环境和可追溯的变更原因；第一次始终预检：

```bash
python3 <skill-dir>/scripts/db_apply.py \
  --env "<prod|test>" --service "<service>" \
  --reason "<change reason>" --sql-file "<sql-file>"
```

预检会输出精确 SQL、PaaS group、工单拆分、执行窗口和 `confirmation_token`；混合 DDL/DML 按输入顺序拆分并依次提交，不合并跨越不同类型的语句。提交顺序不保证平台实际执行顺序；若语句间存在依赖，拆成多次操作，核实前一工单执行完成后再提交下一工单。预检计划以 `600` 权限保存到用户私有目录。计划同时绑定 resolved profile 与 PaaS 提交目标；确认提交先校验 PaaS Cookie，随后才一次性消费 token，并立即将落盘记录收缩为不含 SQL、请求体或工单元数据的消费时间戳标记。SQL、服务、profile、目标或拆分参数变化时必须重新预检；提交失败时先核对 PaaS 工单，不能盲目重试。标记保留七天后会在后续预检时清理。向用户展示这些信息，要求逐项核对拆分后的语句顺序，等待确认完全一致后，才可提交：

```bash
python3 <skill-dir>/scripts/db_apply.py \
  --env "<prod|test>" --service "<service>" \
  --reason "<change reason>" --sql-file "<sql-file>" \
  --submit --confirm "<confirmation_token>"
```

测试环境也必须预检和确认，因为平台可能立即执行。提交成功仅代表平台返回配置的工单标识。审批、立即执行和撤回先运行带 `--action <approve|execute|recall> --id <task-id>` 的预检；其计划同样绑定 profile、PaaS action 契约和精确请求体，确认 token 一次性消费。确认后再执行同一命令并传 `--confirm`；失败时先核对 PaaS 工单，不能重放 token。

## 配置

运行 `python3 <skill-dir>/scripts/setup.py --init` 会创建用户私有配置 `~/.service-ops/config.yaml`，并设置权限为 `600`；SLS 的 project、region/endpoint、AK、SK，PaaS Cookie、HTTP 契约（请求头、端点、字段映射）、测试库密码和日志识别、脱敏正则都在这里。macOS Keychain 的同 profile 凭据优先，配置文件兜底；不读取环境变量。SLS 连接由内置 `sls_query.py --doctor` 检查。PaaS 查询成功响应固定为 `[{"columnList": [...], "rows": [...]}]`，其他响应结构暂不支持。脚本会拒绝读取权限过宽或格式无效的配置。每个可直连测试服务必须填写 `services.<service>.test_database`；测试库账号必须只拥有该配置库的最小权限。只使用日志时运行 `setup.py --check --capability sls`；生产查询运行 `paas`，测试库验证运行 `db`，导出运行 `export`，工单运行 `apply`；用 `setup.py --check --capability db --service <service>` 可提前验证该服务的测试库映射和密码；同时使用全部能力才使用默认 `all`。安装依赖前只检查，不自动安装。真实 SLS 查询仅支持 macOS 或 Unix 主线程；Windows 不在支持范围内：

`requirements.txt` 只记录顶层依赖意图；安装与 CI 使用已解析的 `requirements.lock`。

配置以 profile 隔离。模板只提供通用 `default`；可新增以字母开头、仅包含字母、数字、`-`、`_` 的自定义 profile。日常使用默认 profile；其他部署显式传 `--profile <profile>`。全部配置与凭据只从 Keychain 或私有配置文件读取，不读取环境变量。`--env` 仅保留为兼容别名，等同于同名 profile。

```bash
python3 -m pip install -r <skill-dir>/requirements.lock
```

## 行为评测

改动路由、授权或结果呈现时，按 `evals/triggers.json` 检查自动触发、追问与拒绝边界，并按 `evals/skill-behavior.json` 复核执行后的安全与结果呈现。外部 Agent 运行器可按 [评测结果判定](references/evaluation.md) 提交 JSONL 并获得确定性判定。
