#!/usr/bin/env python3
"""service-ops 内置的阿里云 SLS 查询器。"""
import argparse
import json
import os
import re
import signal
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import paas


_REL_RE = re.compile(r"^(\d+)([smhd])$")
_UNIT_SEC = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_META_KEYS = {"content", "_source_", "_time_", "_pack_meta_", "_pack_id_"}
MAX_QUERY_LIMIT = 1000
MAX_UNACKNOWLEDGED_RANGE_SECONDS = 3600
SLS_REQUEST_TIMEOUT_SECONDS = 30
SLS_QUERY_DEADLINE_SECONDS = 60


def supports_hard_deadline():
    return (hasattr(signal, "setitimer") and hasattr(signal, "SIGALRM")
            and threading.current_thread() is threading.main_thread())


def _hard_deadline_expired(_signum, _frame):
    raise TimeoutError("SLS 查询超时。")


@contextmanager
def hard_deadline(seconds=SLS_QUERY_DEADLINE_SECONDS):
    """Interrupt SDK retries when the query's process-level deadline expires."""
    if not supports_hard_deadline():
        raise RuntimeError("当前平台不支持 SLS 硬 deadline；请在 macOS 或 Unix 主线程执行。")
    previous_handler = signal.signal(signal.SIGALRM, _hard_deadline_expired)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    started = time.monotonic()
    try:
        yield
    finally:
        remaining = max(0, previous_timer[0] - (time.monotonic() - started))
        signal.setitimer(signal.ITIMER_REAL, remaining, previous_timer[1])
        signal.signal(signal.SIGALRM, previous_handler)


def profile_env_name(base, profile):
    return paas.profile_env_name(base, profile)


def parse_time(value, now):
    value = value.strip().lower()
    if value == "now":
        return int(now)
    match = _REL_RE.match(value)
    if match:
        return int(now) - int(match.group(1)) * _UNIT_SEC[match.group(2)]
    if value.isdigit():
        return int(value)
    raise ValueError("无效时间：{}；使用 epoch、now 或 1d/6h/30m。".format(value))


def resolve_profile(environment, profile):
    if environment and profile:
        raise ValueError("--env 与 --profile 不能同时使用。")
    return environment or profile or paas.active_profile()


def quote_full_text(value):
    return '"{}"'.format(value.replace("\\", "\\\\").replace('"', '\\"'))


def build_query(query, trace, terms, level):
    if query is not None:
        if trace or terms or level:
            raise ValueError("--query 不能与 --trace、--level 或关键词混用。")
        return query
    parts = ([quote_full_text(trace)] if trace else [])
    parts.extend(quote_full_text(term) for term in terms if term)
    if level:
        parts.append(level)
    return " and ".join(parts) or "*"


def build_index_aware_query(query, trace, terms, level, indexed_fields):
    full_text = build_query(query, trace, terms, level)
    if query is not None:
        return full_text, "raw"
    parts, used_index = [], False
    if trace:
        field = next((key for key in ("traceId", "trace_id", "content.traceId", "content.trace_id")
                      if key in indexed_fields), None)
        parts.append("{}: {}".format(field, quote_full_text(trace)) if field else quote_full_text(trace))
        used_index = bool(field)
    parts.extend(quote_full_text(term) for term in terms if term)
    if level:
        field = next((key for key in ("level", "content.level") if key in indexed_fields), None)
        parts.append("{}: {}".format(field, level) if field else level)
        used_index = used_index or bool(field)
    return " and ".join(parts) or "*", "indexed" if used_index else "fulltext"


def get_indexed_fields(response):
    body = response.get_body() if hasattr(response, "get_body") else response
    keys = body.get("keys", {}) if isinstance(body, dict) else {}
    return set(keys) if isinstance(keys, dict) else set()


def truncation_metadata(log_count, limit, page=None, offset=None):
    if log_count >= limit:
        metadata = {"truncated": True}
        if offset is not None:
            metadata["next_offset"] = offset + limit
        else:
            metadata["next_page"] = (page or 1) + 1
        return metadata
    return None


def get_credentials(profile):
    profile = profile or paas.active_profile()
    paas.set_active_profile(profile)
    access_key = paas._keychain_value("sls-ak") or os.environ.get(profile_env_name("SLS_LOG_AK", profile), "")
    access_secret = paas._keychain_value("sls-sk") or os.environ.get(profile_env_name("SLS_LOG_SK", profile), "")
    if not access_key or not access_secret:
        raise ValueError("未找到 SLS AK/SK；请写入 service-ops Keychain 或设置 SLS_LOG_AK/SLS_LOG_SK。")
    return access_key, access_secret


def resolve_connection(profile, project, region, endpoint, config=None):
    profile = profile or paas.active_profile()
    settings = (config if config is not None else paas.load_config(profile)).get("sls", {})
    resolved_project = project or settings.get("project") or os.environ.get(profile_env_name("SLS_LOG_PROJECT", profile))
    resolved_endpoint = endpoint or (settings.get("endpoint") if region is None else None) or os.environ.get(profile_env_name("SLS_LOG_ENDPOINT", profile))
    resolved_region = region or settings.get("region") or os.environ.get(profile_env_name("SLS_LOG_REGION", profile))
    if not resolved_project:
        raise ValueError("当前 profile 未配置 SLS project。")
    if not resolved_endpoint and not resolved_region:
        raise ValueError("当前 profile 未配置 SLS region 或 endpoint。")
    return resolved_project, resolved_region, resolved_endpoint


def resolve_logstore(logstore, cwd=None):
    if logstore:
        return logstore
    directory = Path(cwd or os.getcwd()).resolve()
    while True:
        candidates = sorted(directory.glob("build_*-service.yml"))
        if len(candidates) == 1:
            return candidates[0].name.removeprefix("build_").removesuffix(".yml")
        if len(candidates) > 1:
            raise ValueError("发现多个 build_*-service.yml；请传 --service。")
        if directory.parent == directory:
            raise ValueError("未找到 build_*-service.yml；请传 --service。")
        directory = directory.parent


def flatten_contents(raw):
    flat = {key: value for key, value in raw.items() if key not in _META_KEYS}
    content = raw.get("content")
    if isinstance(content, str) and content.lstrip().startswith("{"):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                flat.update(parsed)
        except ValueError:
            flat["content"] = content
    elif content is not None:
        flat["content"] = content
    return flat


def require_sdk():
    try:
        from aliyun.log import LogClient
        return LogClient
    except ImportError as error:
        raise RuntimeError("缺少 aliyun-log-python-sdk；请执行 python3 -m pip install -r requirements.txt。") from error


def set_remaining_request_timeout(client, started, monotonic):
    remaining = SLS_QUERY_DEADLINE_SECONDS - (monotonic() - started)
    if remaining <= 0:
        raise TimeoutError("SLS 查询超时。")
    client.timeout = min(SLS_REQUEST_TIMEOUT_SECONDS, remaining)


def call_with_deadline(client, started, monotonic, method, *args, **kwargs):
    set_remaining_request_timeout(client, started, monotonic)
    result = getattr(client, method)(*args, **kwargs)
    set_remaining_request_timeout(client, started, monotonic)
    return result


def doctor_result(client, project, logstore, now=None, monotonic=time.monotonic, deadline_started=None):
    """Check metadata and perform one bounded read without exposing a log payload."""
    to_time = int(now if now is not None else time.time())
    from_time = max(0, to_time - 300)
    started = monotonic() if deadline_started is None else deadline_started
    call_with_deadline(client, started, monotonic, "get_logstore", project, logstore)
    indexed = get_indexed_fields(call_with_deadline(client, started, monotonic, "get_index_config", project, logstore))
    response = call_with_deadline(client, started, monotonic, "get_logs", project, logstore, from_time, to_time,
                                  query="*", line=1, offset=0, reverse=True)
    logs = response.get_logs()
    return {"status": "ok", "project": project, "logstore": logstore,
            "indexed_fields": sorted(indexed), "read_probe": {"line_limit": 1,
            "matched_rows": len(logs), "duration_ms": int((monotonic() - started) * 1000)}}


def dry_run_result(args, from_time, to_time, query, query_mode):
    """Describe a bounded query without loading configuration or contacting SLS."""
    offset = args.offset if args.offset is not None else ((args.page or 1) - 1) * args.limit
    return {
        "status": "dry_run",
        "execution": False,
        "profile": args.profile,
        "project": args.project,
        "logstore": args.logstore,
        "time_range": {"from": from_time, "to": to_time, "duration_seconds": to_time - from_time},
        "query": query,
        "query_mode": query_mode,
        "limit": args.limit,
        "offset": offset,
        "reverse": args.reverse,
        "next_step": "确认范围和查询后，移除 --dry-run 再执行。",
    }


def fetch_logs(client, project, logstore, from_time, to_time, query, limit, offset=0, reverse=False,
               monotonic=time.monotonic, deadline_started=None):
    """Collect a bounded page sequence without exceeding the query deadline."""
    started, logs = (monotonic() if deadline_started is None else deadline_started), []
    set_remaining_request_timeout(client, started, monotonic)
    pages = iter(client.get_log_all(project, logstore, from_time, to_time, query=query,
                                    reverse=reverse, offset=offset))
    while len(logs) < limit:
        set_remaining_request_timeout(client, started, monotonic)
        try:
            page = next(pages)
        except StopIteration:
            break
        logs.extend(page.get_logs())
        set_remaining_request_timeout(client, started, monotonic)
    return logs[:limit]


def build_parser():
    parser = argparse.ArgumentParser(description="查询阿里云 SLS 日志")
    parser.add_argument("terms", nargs="*", help="全文关键词")
    parser.add_argument("--env", help="兼容别名：等同于 --profile")
    parser.add_argument("--trace")
    parser.add_argument("--level", type=str.upper, choices=("ERROR", "WARN", "INFO", "DEBUG"))
    parser.add_argument("--query", help="原生 SLS 查询")
    parser.add_argument("--project")
    parser.add_argument("--service", "--logstore", dest="logstore")
    parser.add_argument("--region")
    parser.add_argument("--endpoint")
    parser.add_argument("--profile")
    parser.add_argument("--from", dest="from_time", default="15m")
    parser.add_argument("--to", default="now")
    parser.add_argument("--limit", type=int, default=100)
    pagination = parser.add_mutually_exclusive_group()
    pagination.add_argument("--page", type=int)
    pagination.add_argument("--offset", type=int)
    parser.add_argument("--timezone", default="Asia/Singapore")
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--allow-wide-range", action="store_true", help="确认执行超过 1 小时的查询")
    parser.add_argument("--raw", "--jsonl", dest="jsonl", action="store_true", help="输出脱敏 JSONL")
    parser.add_argument("--analysis", dest="jsonl", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="仅输出查询计划，不读取配置、凭据或 SLS")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.limit < 1 or args.limit > MAX_QUERY_LIMIT or (args.page is not None and args.page < 1) or (args.offset is not None and args.offset < 0):
        parser.error("--limit 必须为 1 到 {} 的整数；--page 和 --offset 必须为有效正数。".format(MAX_QUERY_LIMIT))
    if args.doctor and (args.dry_run or args.terms or args.trace or args.level or args.query or args.jsonl):
        parser.error("--doctor 只能与路由参数一起使用。")
    try:
        args.profile = resolve_profile(args.env, args.profile)
        build_query(args.query, args.trace, args.terms, args.level)
        now = time.time()
        from_ts, to_ts = parse_time(args.from_time, now), parse_time(args.to, now)
        if from_ts >= to_ts:
            raise ValueError("--from 必须早于 --to。")
        args.logstore = resolve_logstore(args.logstore)
    except ValueError as error:
        parser.error(str(error))
    if args.dry_run:
        query, query_mode = build_index_aware_query(args.query, args.trace, args.terms, args.level, set())
        print(json.dumps(dry_run_result(args, from_ts, to_ts, query, query_mode), ensure_ascii=False))
        return
    if to_ts - from_ts > MAX_UNACKNOWLEDGED_RANGE_SECONDS and not args.allow_wide_range:
        parser.error("查询范围超过 1 小时；先 dry-run 确认范围，再传 --allow-wide-range 执行。")
    try:
        with hard_deadline():
            query_started = time.monotonic()
            try:
                timezone = ZoneInfo(args.timezone)
                config = paas.load_config(args.profile)
                redaction_patterns = paas.log_analysis_rules(config)["redaction_patterns"]
                project, region, endpoint = resolve_connection(args.profile, args.project, args.region, args.endpoint, config)
                access_key, access_secret = get_credentials(args.profile)
                client = require_sdk()(endpoint or "{}.log.aliyuncs.com".format(region), access_key, access_secret)
                set_remaining_request_timeout(client, query_started, time.monotonic)
            except TimeoutError:
                parser.error("SLS 查询超过 {} 秒；请缩小范围后重试。".format(SLS_QUERY_DEADLINE_SECONDS))
            except (ImportError, RuntimeError, ValueError, ZoneInfoNotFoundError) as error:
                parser.error(str(error))
            if args.doctor:
                try:
                    result = doctor_result(client, project, args.logstore, deadline_started=query_started)
                except TimeoutError:
                    parser.error("SLS doctor 超过 {} 秒；请缩小范围后重试。".format(SLS_QUERY_DEADLINE_SECONDS))
                except Exception as error:
                    parser.error("SLS doctor 失败：{}".format(type(error).__name__))
                print(json.dumps(result, ensure_ascii=False))
                return
            try:
                indexed = get_indexed_fields(call_with_deadline(client, query_started, time.monotonic,
                                                                 "get_index_config", project, args.logstore))
            except TimeoutError:
                parser.error("SLS 查询超过 {} 秒；请缩小范围后重试。".format(SLS_QUERY_DEADLINE_SECONDS))
            except Exception:
                indexed = set()
            args.query, _ = build_index_aware_query(args.query, args.trace, args.terms, args.level, indexed)
            offset = args.offset if args.offset is not None else ((args.page or 1) - 1) * args.limit
            try:
                logs = fetch_logs(client, project, args.logstore, from_ts, to_ts, args.query, args.limit,
                                  offset=offset, reverse=args.reverse, deadline_started=query_started)
            except TimeoutError:
                parser.error("SLS 查询超过 {} 秒；请缩小范围后重试。".format(SLS_QUERY_DEADLINE_SECONDS))
            except Exception as error:
                parser.error("SLS API 失败：{}".format(type(error).__name__))
    except TimeoutError:
        parser.error("SLS 查询超过 {} 秒；请缩小范围后重试。".format(SLS_QUERY_DEADLINE_SECONDS))
    except RuntimeError as error:
        parser.error(str(error))
    for log in logs[:args.limit]:
        flat, timestamp = flatten_contents(dict(log.get_contents())), log.get_time()
        flat = paas.redact_log_fields(flat, redaction_patterns)
        if args.jsonl:
            print(json.dumps({"_time_": timestamp, **flat}, ensure_ascii=False))
        else:
            message = flat.get("message", flat.get("content", " ".join("{}={}".format(k, v) for k, v in flat.items())))
            print("{} [{}] {}".format(datetime.fromtimestamp(int(timestamp), timezone).strftime("%m-%d %H:%M:%S %Z"),
                                        flat.get("level", ""), str(message).rstrip()))
    metadata = truncation_metadata(len(logs), args.limit, args.page, offset if args.offset is not None else None)
    if metadata:
        print(json.dumps(metadata), file=sys.stderr)


if __name__ == "__main__":
    main()
