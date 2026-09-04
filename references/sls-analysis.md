# SLS 分析查询计划

只在用户请求错误趋势、Top-N、分组、分位数或分布时读取本文件。此阶段只输出计划，不执行查询。

## 先确认的最小信息

1. 服务或 Logstore、环境或 profile。
2. 分析目标：趋势、Top-N、分组、P95 或分布。
3. 时间范围：未给出时，聚合计划默认最近 1 小时；超过 1 小时必须先获得明确确认。
4. 分析字段是否已知；未知时，建议先运行 `sls_query.py --doctor` 检查索引，不猜测业务字段。

## 计划输出

输出目标、目标服务、时间范围、候选查询、结果上限、索引或扫描风险，以及执行前仍需确认的事项。计划不构成执行证据。

## 通用查询骨架

以下仅为待确认的 SLS 查询骨架；将 `<field>` 和 `<value>` 替换为用户已确认或已验证索引字段。

| 目标 | 候选查询 |
|---|---|
| 错误趋势 | `<field>:<value> | SELECT date_trunc('minute', __time__) AS minute, count(*) AS total FROM log GROUP BY minute ORDER BY minute LIMIT 60` |
| Top-N | `<field>:<value> | SELECT <dimension>, count(*) AS total FROM log GROUP BY <dimension> ORDER BY total DESC LIMIT 20` |
| P95 | `<field>:<value> | SELECT approx_percentile(<metric>, 0.95) AS p95 FROM log LIMIT 1` |
| 分布 | `<field>:<value> | SELECT <dimension>, count(*) AS total FROM log GROUP BY <dimension> ORDER BY total DESC LIMIT 20` |

先用 dry-run 验证计划；该命令不读取本地配置、凭据或 SLS：

```bash
python3 <skill-dir>/scripts/sls_query.py --dry-run --service "<service-or-logstore>" \
  --from "<candidate-range>" --query "<candidate-query>" --limit <bounded-limit>
```

确认后移除 `--dry-run` 执行；候选范围超过 1 小时时还需显式附加 `--allow-wide-range`。只摘要脱敏后的统计结果；若索引、权限、采样或截断不完整，结论必须说明局限。
