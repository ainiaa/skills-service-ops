#!/usr/bin/env python3
"""分析由内置 SLS 查询器输出的统一结构化日志。"""
import argparse
import json
import re
import sys

import paas


def build_timeline(logs, redaction_patterns=None):
    events = []
    for log in logs:
        level = log.get("level", "")
        raw_message = log.get("message", "")
        message = (paas.redact_text(raw_message, redaction_patterns)
                   if redaction_patterns is not None else str(raw_message))
        if level in ("ERROR", "WARN") or any(word in message.lower() for word in ("begin", "start", "end")):
            events.append({"time": log.get("time", ""), "level": level, "message": message[:300]})
    return sorted(events, key=lambda item: item["time"])


def analyze(data, related_service_pattern=None, entity_patterns=None, redaction_patterns=None):
    validate_collector_data(data)
    errors, warnings, logs = [], [], []
    failed, truncated = [], []
    for service, item in data.get("services", {}).items():
        if item.get("status") == "error":
            failed.append(service)
            continue
        if item.get("truncated"):
            truncated.append(service)
        errors.extend(item.get("error_logs", []))
        warnings.extend(item.get("warn_logs", []))
        logs.extend(item.get("context_logs", []))
    related = set()
    exceptions = []
    entities = {name: set() for name in (entity_patterns or {})}
    suggested_sql = []
    for log in errors:
        raw_message = log.get("throwable", "") or log.get("message", "")
        message = (paas.redact_text(raw_message, redaction_patterns)
                   if redaction_patterns is not None else str(raw_message))
        match = re.search(r"([\w.]+(?:Exception|Error))(?::\s*(.*))?", message)
        if match:
            exceptions.append({"type": match.group(1), "message": (match.group(2) or "")[:200], "time": log.get("time", "")})
        if "DuplicateKey" in message:
            suggested_sql.append({"purpose": "验证唯一键冲突", "sql": "SELECT /* 指定字段 */ FROM <table> WHERE <unique_key>=<value> LIMIT 10;"})
    for log in logs + errors:
        raw_message = log.get("message", "")
        message = (paas.redact_text(raw_message, redaction_patterns)
                   if redaction_patterns is not None else str(raw_message))
        if related_service_pattern:
            for match in re.finditer(related_service_pattern, message):
                related.add(match.group(1) if match.lastindex else match.group(0))
        for name, pattern in (entity_patterns or {}).items():
            for match in re.finditer(pattern, message):
                entities[name].add(match.group(1) if match.lastindex else match.group(0))
    return {"summary": {"error_count": len(errors), "warn_count": len(warnings),
                        "evidence_failed_services": failed, "truncated_services": truncated},
            "exceptions": exceptions, "timeline": build_timeline(logs + errors + warnings, redaction_patterns)[:50],
            "entities": {key: sorted(value) for key, value in entities.items()},
            "related_services": sorted(related), "suggested_sql": suggested_sql}


def analysis_config(profile=None):
    """Load optional pattern configuration without blocking standalone JSON analysis."""
    if not paas.CONFIG_PATH.exists():
        return {}
    config = paas.load_config(profile)
    return config


def validate_collector_data(data):
    services = data.get("services") if isinstance(data, dict) else None
    if not isinstance(services, dict):
        raise ValueError("日志输入必须包含 services 对象。")
    for service, item in services.items():
        if not isinstance(item, dict):
            raise ValueError("服务 {} 的日志输入必须是对象。".format(service))
        if item.get("status") not in ("ok", "error"):
            raise ValueError("服务 {} 的 status 必须是 ok 或 error。".format(service))
        for field in ("error_logs", "warn_logs", "context_logs"):
            logs = item.get(field, [])
            if not isinstance(logs, list) or not all(isinstance(log, dict) for log in logs):
                raise ValueError("服务 {} 的 {} 必须是日志对象列表。".format(service, field))


def main(argv=None):
    parser = argparse.ArgumentParser(description="分析 service-ops 结构化日志")
    parser.add_argument("--profile", help="覆盖采集结果中的配置 profile")
    parser.add_argument("--redact", action="store_true", help="按配置规则脱敏分析结果")
    args = parser.parse_args(argv)
    try:
        data = json.load(sys.stdin)
        validate_collector_data(data)
        embedded_profile = data.get("profile")
        config = analysis_config(args.profile or embedded_profile)
        rules = paas.log_analysis_rules(config)
        redaction_patterns = rules["redaction_patterns"] if args.redact else None
        result = analyze(data, rules["related_service_pattern"], rules["entity_patterns"], redaction_patterns)
    except ValueError as error:
        parser.error(str(error))
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
