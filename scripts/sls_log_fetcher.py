#!/usr/bin/env python3
"""通过内置 SLS 查询器获取 TraceId 证据，并转换为分析格式。"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import paas
import sls_query


WIDE_RANGE_ERROR = "查询范围超过 1 小时"
SLS_QUERY_TIMEOUT_SECONDS = 60


def local_sls_query_script():
    return Path(__file__).with_name("sls_query.py")


def build_sls_query_command(script, trace_id, service, env, profile, from_time, to_time, limit, allow_wide_range=False):
    command = [sys.executable, str(script), "--trace", trace_id, "--service", service,
               "--from", from_time, "--to", to_time, "--limit", str(limit), "--raw"]
    if env:
        command.extend(["--env", env])
    if profile:
        command.extend(["--profile", profile])
    if allow_wide_range:
        command.append("--allow-wide-range")
    return command


def normalize_event(raw):
    event = {key: raw[key] for key in ("traceId", "trace_id", "spanId", "span_id", "requestId", "request_id")
             if key in raw}
    timestamp = raw.get("_time_", raw.get("time", ""))
    if isinstance(timestamp, (int, float)) or (isinstance(timestamp, str) and timestamp.isdigit()):
        event["time"] = datetime.fromtimestamp(int(timestamp), timezone.utc).isoformat()
    else:
        event["time"] = str(timestamp)
    event["level"] = str(raw.get("level", ""))
    event["message"] = paas.redact_text(raw.get("message", raw.get("content", "")))
    if raw.get("throwable") is not None:
        event["throwable"] = paas.redact_text(raw["throwable"])
    return event


def is_truncated(stderr):
    for line in stderr.splitlines():
        try:
            metadata = json.loads(line)
        except ValueError:
            continue
        if isinstance(metadata, dict) and metadata.get("truncated") is True:
            return True
    return False


def fetch_service(command, runner=subprocess.run):
    try:
        result = runner(command, capture_output=True, text=True, check=False, timeout=SLS_QUERY_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "SLS 日志查询超时；请缩小范围后重试。"}
    except OSError:
        return {"status": "error", "error": "SLS 日志查询失败；请运行 sls_query.py --doctor 检查配置、凭据和权限。"}
    if result.returncode != 0:
        if WIDE_RANGE_ERROR in result.stderr:
            return {"status": "error", "error": "SLS 日志查询范围超过 1 小时；先运行 sls_query.py --dry-run 确认范围，再传 --allow-wide-range 执行。"}
        return {"status": "error", "error": "SLS 日志查询失败；请运行 sls_query.py --doctor 检查配置、凭据和权限。"}
    try:
        logs = [normalize_event(json.loads(line)) for line in result.stdout.splitlines() if line.strip()]
    except (TypeError, ValueError):
        return {"status": "error", "error": "SLS 日志查询返回格式无效。"}
    errors = [log for log in logs if log["level"].upper() == "ERROR"]
    warnings = [log for log in logs if log["level"].upper() == "WARN"]
    return {"status": "ok", "error_logs": errors, "warn_logs": warnings,
            "context_logs": [log for log in logs if log not in errors and log not in warnings],
            "all_logs_count": len(logs), "truncated": is_truncated(result.stderr)}


def main():
    parser = argparse.ArgumentParser(description="通过内置 SLS 查询器拉取 TraceId 日志")
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--service", required=True, help="服务或 Logstore")
    environment = parser.add_mutually_exclusive_group()
    environment.add_argument("--env", help="兼容别名：等同于 --profile")
    environment.add_argument("--profile", help="高级凭据 profile")
    parser.add_argument("--related-services", nargs="*", default=[])
    parser.add_argument("--from", dest="from_time", default="15m")
    parser.add_argument("--to", default="now")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--allow-wide-range", action="store_true", help="确认执行超过 1 小时的查询")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > sls_query.MAX_QUERY_LIMIT:
        parser.error("--limit 必须为 1 到 {} 的整数。".format(sls_query.MAX_QUERY_LIMIT))
    profile = sls_query.resolve_profile(args.env, args.profile)
    script = local_sls_query_script()
    services = dict.fromkeys([args.service] + args.related_services)
    output = {"trace_id": args.trace_id, "profile": profile, "collector": "service-ops", "services": {}}
    for service in services:
        command = build_sls_query_command(script, args.trace_id, service, args.env, args.profile,
                                          args.from_time, args.to, args.limit, args.allow_wide_range)
        fetched = fetch_service(command)
        fetched["logstore"] = service
        output["services"][service] = fetched
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
