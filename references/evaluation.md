# 评测结果判定

外部 Agent 运行器负责对 `evals/triggers.json` 或 `evals/skill-behavior.json` 的每个 input 产生真实结果；本项目只确定性判定结果，不运行模型或外部系统。

触发路由场景的每行结果为 JSONL，字段为 `id`、`actual_action` 和 `actual_route`，值必须与对应预期一致。例如：

```json
{"id":"sls-log-search","actual_action":"activate","actual_route":"sls_query.py"}
```

运行：

```bash
python3 <skill-dir>/scripts/eval_contract.py --results <runner-results.jsonl>
```

行为场景使用 `actual_route`、`actual_asked` 和 `actual_output`（均为字符串或字符串列表）；例如 `actual_asked` 记录实际追问字段，`actual_output` 记录最终输出中的标志词。执行时指定契约：

```bash
python3 <skill-dir>/scripts/eval_contract.py \
  --cases <skill-dir>/evals/skill-behavior.json --results <runner-results.jsonl>
```

输出 `status: passed` 表示全部场景一致；`failed` 会列出缺失、动作不符、路由不符、追问不足、禁止路径或输出不符的 case，`invalid_results` 会列出重复或未知的结果 ID。重复 case ID 是无效契约。任一失败都会返回非零退出码。该判定器不替代真实 Agent 运行，也不把计划文本视为执行证据。
