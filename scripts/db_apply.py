#!/usr/bin/env python3
"""预检并提交 PaaS DDL/DML 工单；默认不提交。"""
import argparse
import hashlib
import json
import re
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile

import paas


DDL = {"CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME", "COMMENT"}
DML = {"INSERT", "UPDATE", "DELETE", "MERGE", "REPLACE"}
DESTRUCTIVE_DDL = {"DROP", "TRUNCATE"}
_TOKEN = re.compile(r"^apply-[0-9a-f]{32}$")
PREFLIGHT_RETENTION = timedelta(days=7)


class SubmissionFailure(RuntimeError):
    def __init__(self, submitted=()):
        super().__init__("PaaS 工单提交失败。")
        self.submitted = list(submitted)


def is_request_error(error):
    try:
        import requests
    except ImportError:
        return False
    return isinstance(error, requests.RequestException)


def build_task_op(action, task_id, task_actions, approval_message="确认通过"):
    contract = task_actions.get(action, {})
    endpoint, id_field = contract.get("endpoint"), contract.get("id_field")
    if not endpoint or not id_field:
        raise ValueError("未知工单操作：{}".format(action))
    body = {id_field: task_id}
    if contract.get("message_field"):
        body[contract["message_field"]] = approval_message
    return endpoint, body


def build_task_tickets(action, task_ids, task_actions, approval_message):
    return [{"id": task_id, "endpoint": endpoint, "body": body}
            for task_id in task_ids
            for endpoint, body in [build_task_op(action, task_id, task_actions, approval_message)]]


def parse_task_ids(value):
    ids = [part.strip() for part in value.split(",") if part.strip()]
    if not ids or not all(item.isdigit() for item in ids):
        raise ValueError("工单 id 必须是逗号分隔的数字。")
    return [int(item) for item in ids]


def split_statements(sql_text):
    statements, current, quote, escaped = [], [], None, False
    line_comment, block_comment, index = False, False, 0
    while index < len(sql_text):
        char = sql_text[index]
        next_char = sql_text[index + 1] if index + 1 < len(sql_text) else ""
        current.append(char)
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif line_comment:
            if char == "\n":
                line_comment = False
        elif block_comment:
            if char == "*" and next_char == "/":
                current.append(next_char)
                index += 1
                block_comment = False
        elif paas.is_mysql_line_comment(sql_text, index):
            current.append(next_char)
            index += 1
            line_comment = True
        elif char == "#":
            line_comment = True
        elif char == "/" and next_char == "*":
            current.append(next_char)
            index += 1
            block_comment = True
        elif char in ("'", '"', "`"):
            quote = char
        elif char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        index += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail if tail.endswith(";") else tail + ";")
    return statements


def has_top_level_where(statement):
    code, depth = paas._sql_code(statement), 0
    for token in re.findall(r"\b[A-Za-z_]+\b|[()]", code):
        if token == "(":
            depth += 1
        elif token == ")":
            depth = max(0, depth - 1)
        elif token.upper() == "WHERE" and depth == 0:
            return True
    return False


def plan_changes(sql_text, allow_destructive=False):
    plan = {"ddl": [], "dml": []}
    for statement in split_statements(sql_text):
        match = re.search(r"\b([A-Za-z]+)\b", paas._sql_code(statement))
        keyword = match.group(1).upper() if match else ""
        if keyword in DDL:
            if keyword in DESTRUCTIVE_DDL and not allow_destructive:
                raise ValueError("{} 需要显式传入 --allow-destructive。".format(keyword))
            plan["ddl"].append(statement)
        elif keyword in DML:
            if keyword in {"UPDATE", "DELETE"} and not has_top_level_where(statement):
                raise ValueError("{} 必须包含 WHERE 条件。".format(keyword))
            plan["dml"].append(statement)
        else:
            raise ValueError("不支持提交的 SQL：{}".format(statement[:80]))
    if not plan["ddl"] and not plan["dml"]:
        raise ValueError("未解析到 DDL 或 DML。")
    return plan


def confirmation_token(env, service, group, reason, statements, nonce=None):
    if nonce is not None:
        statements = {"plan": statements, "nonce": nonce}
    payload = json.dumps({"env": env, "service": service, "group": group, "reason": reason, "statements": statements}, ensure_ascii=False, separators=(",", ":"))
    return "apply-" + hashlib.sha256(payload.encode()).hexdigest()[:32]


def preflight_path(token):
    if not _TOKEN.fullmatch(token or ""):
        raise ValueError("确认指纹格式无效。")
    return paas.CONFIG_PATH.parent / "preflights" / "{}.json".format(token)


def submitted_preflight_path(token):
    return preflight_path(token).with_suffix(".submitted")


def cleanup_submitted_preflights(now=None):
    """Remove consumed plans after their short operational retention period."""
    directory = paas.CONFIG_PATH.parent / "preflights"
    if not directory.exists():
        return 0
    cutoff = (now or datetime.now()) - PREFLIGHT_RETENTION
    removed = 0
    for path in directory.glob("apply-*.submitted"):
        if not _TOKEN.fullmatch(path.stem):
            continue
        try:
            if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def _write_private_preflight(path, value):
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            json.dump(value, file, ensure_ascii=False, separators=(",", ":"))
        temporary.replace(path)
        path.chmod(0o600)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_preflight(token, request, tickets, nonce=None):
    path = preflight_path(token)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    cleanup_submitted_preflights()
    _write_private_preflight(path, {"request": request, "tickets": tickets, "nonce": nonce})


def read_preflight(path):
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError("未找到有效预检计划；请重新预检后再提交。") from error
    if (not isinstance(stored, dict) or not isinstance(stored.get("request"), dict)
            or not isinstance(stored.get("tickets"), list)
            or stored.get("nonce") is not None and not isinstance(stored.get("nonce"), str)):
        raise ValueError("预检计划格式无效；请重新预检后再提交。")
    return stored


def load_preflight(token):
    path = preflight_path(token)
    if not path.exists() and submitted_preflight_path(token).exists():
        raise ValueError("确认指纹已提交或提交状态未知；请先核对 PaaS 工单。")
    return read_preflight(path)


def claim_preflight(token):
    path, submitted = preflight_path(token), submitted_preflight_path(token)
    if submitted.exists():
        raise ValueError("确认指纹已提交或提交状态未知；请先核对 PaaS 工单。")
    try:
        path.replace(submitted)
    except OSError as error:
        raise ValueError("未找到有效预检计划；请重新预检后再提交。") from error
    stored = read_preflight(submitted)
    try:
        _write_private_preflight(submitted, {"consumed_at": datetime.now().isoformat(timespec="seconds")})
    except OSError as error:
        raise ValueError("无法保护已消费预检计划；请先核对 PaaS 工单。") from error
    return stored


def build_apply_body(statements, group, reason, paas_env, start, end, contract):
    fields = contract.get("fields", {})
    required = ("sql", "service", "group", "reason", "envs")
    if not contract.get("service_name") or any(not fields.get(name) for name in required):
        raise ValueError("PaaS apply_contract 未配置完整字段。")
    body = {fields["sql"]: "\n".join(statements) + "\n", fields["service"]: contract["service_name"],
            fields["group"]: group, fields["reason"]: reason, fields["envs"]: [paas_env]}
    if start and end:
        if not fields.get("start") or not fields.get("end"):
            raise ValueError("PaaS apply_contract 未配置执行窗口字段。")
        body[fields["start"]], body[fields["end"]] = start, end
    return body


def _read_sql(args):
    return Path(args.sql_file).read_text(encoding="utf-8") if args.sql_file else args.sql


def _tickets(plan, group, reason, paas_env, env, batch_size, contract):
    schedule = None if env == "test" else (
        (datetime.now() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
        (datetime.now() + timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S"),
    )
    tickets = []
    for kind, statements in (("DDL", plan["ddl"]), ("DML", plan["dml"])):
        for index in range(0, len(statements), batch_size):
            chunk = statements[index:index + batch_size]
            tickets.append({"kind": kind, "statements": chunk,
                            "body": build_apply_body(chunk, group, reason, paas_env, *(schedule or (None, None)), contract)})
    return tickets


def apply_id(response, field):
    if not field or not isinstance(response, dict) or not response.get(field):
        raise RuntimeError("PaaS 未返回配置的工单标识，工单未确认提交成功。")
    return str(response[field])


def _submit(tickets, config, cookie):
    paas_config = config.get("paas", {})
    api_base = paas_config.get("apply_api_base", "")
    endpoints = paas_config.get("apply_endpoints", {})
    response_id_field = paas_config.get("apply_response_id_field", "")
    if not api_base or not response_id_field:
        raise ValueError("PaaS 提交端点或响应标识字段未配置。")
    session = paas.build_session()
    headers = paas.api_headers(config, cookie)
    submitted = []
    for ticket in tickets:
        endpoint = endpoints.get(ticket["kind"].lower(), "")
        if not endpoint:
            raise ValueError("PaaS {} 提交端点未配置。".format(ticket["kind"]))
        try:
            response = session.post(api_base.rstrip("/") + "/" + endpoint, json=ticket["body"], headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            submitted.append({"kind": ticket["kind"], "apply_id": apply_id(data, response_id_field)})
        except Exception as error:
            if is_request_error(error) or isinstance(error, (OSError, RuntimeError, ValueError)):
                raise SubmissionFailure(submitted) from error
            raise
    return submitted


def main():
    parser = argparse.ArgumentParser(description="预检或提交 PaaS DDL/DML 工单")
    parser.add_argument("--env", choices=["prod", "test"])
    parser.add_argument("--service")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--sql")
    source.add_argument("--sql-file")
    parser.add_argument("--reason")
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--allow-destructive", action="store_true", help="允许 DROP 或 TRUNCATE；仍需预检与确认")
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--action", choices=["apply", "approve", "execute", "recall"], default="apply")
    parser.add_argument("--id", dest="task_ids")
    parser.add_argument("--approval-message", default="确认通过")
    parser.add_argument("--profile")
    args = parser.parse_args()
    try:
        paas.set_active_profile(args.profile)
    except ValueError as error:
        parser.error(str(error))
    if args.batch_size < 1:
        parser.error("--batch-size 必须大于 0。")
    if args.action != "apply":
        if not args.task_ids:
            parser.error("工单操作需要 --id。")
        try:
            ids = parse_task_ids(args.task_ids)
            config = paas.load_config()
            paas_config = config.get("paas", {})
            base = paas_config.get("task_api_base", "")
            actions = paas_config.get("task_actions", {})
            if not base:
                raise ValueError("PaaS task_api_base 未配置。")
            target = {"api_base": base, "actions": actions}
            request = {"profile": paas.active_profile(), "action": args.action, "ids": ids,
                       "approval_message": args.approval_message, "target": target}
            if args.confirm:
                stored = load_preflight(args.confirm)
                token = confirmation_token(args.action, "task", base, args.approval_message,
                                           {"request": stored["request"], "tickets": stored["tickets"]}, stored.get("nonce"))
                if args.confirm != token or stored["request"] != request:
                    raise ValueError("确认指纹与预检计划不一致；请重新预检后再提交。")
                cookie = paas.get_cookie()
                if not cookie:
                    raise ValueError("未找到 PaaS Cookie。")
                tickets = claim_preflight(args.confirm)["tickets"]
            else:
                tickets = build_task_tickets(args.action, ids, actions, args.approval_message)
                nonce = secrets.token_hex(16)
                token = confirmation_token(args.action, "task", base, args.approval_message,
                                           {"request": request, "tickets": tickets}, nonce)
                save_preflight(token, request, tickets, nonce)
                paas.print_json({"action": args.action, "ids": ids, "confirmation_token": token})
                return
            session = paas.build_session()
            headers = paas.api_headers(config, cookie)
            completed = []
            for ticket in tickets:
                try:
                    response = session.post(base + ticket["endpoint"], json=ticket["body"], headers=headers, timeout=60)
                    response.raise_for_status()
                    completed.append(ticket["id"])
                except Exception as error:
                    if is_request_error(error) or isinstance(error, (OSError, RuntimeError, ValueError)):
                        paas.print_json({"error": "PaaS 工单操作失败。", "completed_ids": completed}, stream=sys.stderr)
                        raise SystemExit(2)
                    raise
            paas.print_json({"action": args.action, "ids": ids, "status": "submitted"})
            return
        except (ImportError, OSError, ValueError) as error:
            parser.error(str(error))
    if not args.env or not args.service or not args.reason or not (args.sql or args.sql_file):
        parser.error("apply 需要 --env、--service、--reason 和 --sql 或 --sql-file。")
    try:
        config = paas.load_config()
        group = paas.service_group(config, args.service)
        plan = plan_changes(_read_sql(args), allow_destructive=args.allow_destructive)
        paas_config = config.get("paas", {})
        paas_env = paas_config.get("apply_envs", {}).get(args.env)
        if not paas_env:
            raise ValueError("PaaS apply 环境映射未配置。")
    except (OSError, ValueError, ImportError) as error:
        parser.error(str(error))
    ordered = ["DDL:" + sql for sql in plan["ddl"]] + ["DML:" + sql for sql in plan["dml"]]
    target = {"api_base": paas_config.get("apply_api_base", ""),
              "endpoints": paas_config.get("apply_endpoints", {}),
              "response_id_field": paas_config.get("apply_response_id_field", ""),
              "contract": paas_config.get("apply_contract", {})}
    request = {"profile": paas.active_profile(), "env": args.env, "service": args.service, "group": group,
               "reason": args.reason, "statements": ordered, "batch_size": args.batch_size, "target": target}
    if args.submit:
        try:
            stored = load_preflight(args.confirm)
            token = confirmation_token(args.env, args.service, group, args.reason,
                                       {"request": stored["request"], "tickets": stored["tickets"]}, stored.get("nonce"))
            if args.confirm != token or stored["request"] != request:
                raise ValueError("确认指纹与预检计划不一致；请重新预检后再提交。")
            cookie = paas.get_cookie()
            if not cookie:
                raise ValueError("未找到 PaaS Cookie；请写入 Keychain 或设置 PAAS_COOKIE。")
            stored = claim_preflight(args.confirm)
            tickets = stored["tickets"]
        except (OSError, ValueError) as error:
            parser.error(str(error))
    else:
        try:
            tickets = _tickets(plan, group, args.reason, paas_env, args.env, args.batch_size,
                               paas_config.get("apply_contract", {}))
            nonce = secrets.token_hex(16)
            token = confirmation_token(args.env, args.service, group, args.reason,
                                       {"request": request, "tickets": tickets}, nonce)
            save_preflight(token, request, tickets, nonce)
        except (OSError, ValueError) as error:
            parser.error("无法保存预检计划：{}".format(error))
    preview = {"mode": "submit" if args.submit else "dry-run", "service": args.service, "env": args.env,
               "group": group, "confirmation_token": token, "tickets": tickets}
    if not args.submit:
        paas.print_json(preview)
        return
    try:
        paas.print_json({"submitted": _submit(tickets, config, cookie)})
    except SubmissionFailure as error:
        paas.print_json({"error": "PaaS 工单提交失败。", "submitted": error.submitted}, stream=sys.stderr)
        raise SystemExit(2)
    except (OSError, RuntimeError, ValueError, ImportError):
        paas.print_json({"error": "PaaS 工单提交失败。", "submitted": []}, stream=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
