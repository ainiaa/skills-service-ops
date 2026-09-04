<!-- PDLC-TRACE -->
<!-- 功能ID: F20260902-101243 -->
<!-- 功能名称: service-ops-governance -->
<!-- 阶段: 设计 -->
<!-- 前置文档: docs/01_requirements/prd/F20260902-101243-service-ops-governance-prd.md -->
<!-- 创建时间: 2026-09-02T10:12:43+08:00 -->

# service-ops 运维行为设计

## 1. 范围

本设计记录既有运行行为，不新增 API、数据库表或外部依赖。

## 2. 能力边界

```text
自动发现：日志检索 / TraceId 排障 / 只读验证 / Excel 导出
显式调用：$skills-service-ops + 明确工单意图 → db_apply.py
```

工单不能由自动匹配、已加载的排障上下文或含糊表达触发。工单执行仍经过 SQL 预检、confirmation token 与用户确认。

## 3. 排障证据流

```text
sls_query.py --raw / --jsonl
  → sls_log_fetcher.py（error / warn / context / truncated）
  → log_analyzer.py（evidence_failed_services / truncated_services）
  → 最终报告（已确认 / 待验证 / 证据不完整 / 证据采集失败）
```

`truncated_services` 非空表示查询可能未覆盖全部日志，结论不得表述为已完全确认。

普通日志和 TraceId 查询未给出时间范围时，默认最近 15 分钟；超过 1 小时必须先给出查询计划并取得范围确认。趋势、Top-N、分组、分位数和分布分析先以计划模式明确目标、字段、时间范围、结果上限和索引风险，未经确认不得执行。

每次执行后的汇报依次说明执行范围、已确认结论、证据局限和下一步；未执行的查询不得表述为证据。

采集器将已解析的 profile 写入结构化结果；分析器优先使用该 profile 加载私有识别和脱敏规则。任何输出模式达到或超过查询行数上限时，均需保留 `truncated: true`。SLS 查询、采集器和分析器均先脱敏通用凭据字段；业务脱敏规则由共享链路应用于所有日志出口，且仅从私有配置读取。`setup.py --check --capability sls` 会预先校验全部日志正则；`sls_query.py --doctor` 还会执行最近 5 分钟、最多 1 条且不输出内容的读权限探针；采集器遇到宽范围拒绝时必须保留 `--dry-run` 与 `--allow-wide-range` 的下一步，而不是误导为权限诊断；分析器拒绝不符合采集结构的 JSON，而不是输出 traceback。

`sls_query.py --dry-run` 仅解析 profile、查询、日志库和时间范围，输出固定 JSON 查询计划；该分支在加载配置、读取凭据和创建 SLS 客户端之前返回。外部 Agent 运行器将触发结果写成 JSONL，内置 `eval_contract.py` 对照公开契约判定 action/route，并将重复或未知用例视为无效输入而失败。

变更 SQL 的 `UPDATE` 与 `DELETE` 必须包含顶层 `WHERE`，子查询中的 `WHERE` 不得作为安全条件；SQL 拆分识别引号和注释，避免注释内分号破坏预检。仅当 `--` 后接 ASCII 空白或控制字符时才按 MySQL 行注释处理；MySQL 可执行注释 `/*!...*/` 一律拒绝，不能被剥离后参与只读或工单判断。只读 SELECT 拒绝直接或反引号引用的 `GET_LOCK`、`RELEASE_LOCK`、`SLEEP`、`BENCHMARK`、`LOAD_FILE` 与 `LAST_INSERT_ID`，也拒绝 `INTO @var`、`@var :=`，避免锁和会话状态变更、资源消耗或服务端文件读取。DDL/DML 和 approve/execute/recall 的预检都将精确请求体写入权限为 `600` 的用户私有计划记录，并绑定 resolved profile、对应 PaaS API base 与契约；执行时必须从该记录读取，且当前参数、profile 与目标完全一致。确认时先验证 PaaS Cookie，随后 token 一次性消费并立即将落盘计划重写为仅含消费时间戳的标记；提交失败也保留已消费状态，必须先核对 PaaS 工单。标记保留七天后在下一次预检时清理。Keychain 读取超时为 10 秒，错误或超时后只回退到同一 profile 的环境变量。SLS SDK 请求超时为 30 秒；macOS/Unix 主线程以进程级 60 秒定时器中断整次 SLS 查询，TraceId 采集子进程超时为 60 秒，不支持该定时器的平台拒绝真实查询；SLS SDK 依赖约束为已验证的 0.9.x。SLS 真实查询的单次输出上限为 1000 行，超过 1 小时须先计划并以 `--allow-wide-range` 显式确认。非 default profile 的 PaaS 与测试库环境变量使用 profile 后缀，避免回退到其他 profile 的凭据。评测器同时校验触发和行为契约，并拒绝重复 case ID 或非对象结果行。

## 4. 就绪检查

| 能力 | 必需模块 | 检查内容 |
|---|---|---|
| all | requirements.lock 全部模块 | 所有能力的配置、凭据与运行依赖 |
| paas | requests、pyyaml | PaaS Cookie、查询端点、字段契约，以及 prod/test 环境映射 |
| sls | pyyaml、aliyun-log-python-sdk | SLS 坐标与 AK/SK |
| db | pyyaml、pymysql | 测试库 host、user 与密码；附加 `--service` 时同时校验该服务的 test_database |
| export | requests、pyyaml、openpyxl | PaaS Cookie、查询契约与 Excel 运行依赖 |
| apply | requests、pyyaml | PaaS Cookie、DDL/DML 提交端点、响应标识、字段契约及 prod/test 环境映射 |

`install.sh --capability <name>` 与 `setup.py --check --capability <name>` 均按表中能力检查；未指定时默认 `all`。安装脚本不自动安装依赖或执行外部探针。

工单契约不属于 `paas` 就绪检查范围：工单只能显式调用，且在执行前校验所需端点和字段，避免不使用工单的用户被无关配置阻塞。

## 4.1 独立日志分析

`log_analyzer.py` 的输入是标准 JSON，因此在本地配置文件不存在时仍可独立运行；仅当私有配置文件存在时，才加载其中的服务和实体识别正则。这既保留公开工具的可移植性，也不把内部规则写入代码。

## 5. 安全约束

- Cookie、AK/SK、测试库密码仅从 Keychain 或运行时环境变量读取。
- 生产查询、导出和工单必须获得明确授权；生产导出直接执行命令即为调用者确认，不增加二次 token。
- 测试库账号必须以最小权限限制在每个服务已配置的 test_database；代码拒绝未配置该库名的直连。
- Excel 导出中的字符串若以公式前缀开头，必须作为文本写入，避免在办公软件中执行公式。
- 导出 SQL 的内联参数与文件参数互斥；导出结果行数不得超过已批准的 SQL LIMIT，行结构无效时拒绝写入；Excel 先写同目录临时文件，再原子替换目标文件。
- profile 名称在配置、Keychain 和环境变量路径中使用同一受限格式；分页续取使用与请求方式一致的 page 或 offset 指针。
- 任何采集失败不得被转换为空结果。

## 自审记录

- 自审时间：2026-09-02T10:12:43+08:00
- PRD 覆盖：4/4 功能项均有设计映射。
- API/DB 设计：不适用；本功能不新增接口或数据存储。
- 结论：通过。
