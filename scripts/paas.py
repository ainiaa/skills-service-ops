#!/usr/bin/env python3
"""PaaS 配置、凭据和只读查询的共享实现。"""
import json
import platform
import re
import ssl
import subprocess
from pathlib import Path

CONFIG_PATH = Path.home() / ".service-ops" / "config.yaml"
KEYCHAIN_SERVICE = "service-ops"
KEYCHAIN_TIMEOUT_SECONDS = 10
_ACTIVE_PROFILE = "default"
_PROFILE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_SENSITIVE_LOG_VALUE = re.compile(
    r"(?i)(\b(?:authorization|cookie|token|password|passwd|secret|api[_-]?key|access[_-]?key)\b"
    r"\s*[:=]\s*(?:bearer\s+)?)(\"[^\"]*\"|'[^']*'|[^,\s;]+)"
)
_SENSITIVE_LOG_KEYS = {
    "authorization", "cookie", "set_cookie", "password", "passwd", "secret", "token",
    "access_token", "accesstoken", "refresh_token", "refreshtoken", "id_token", "idtoken",
    "api_key", "apikey", "access_key", "accesskey",
}
_SAFE_SELECT_FUNCTIONS = {
    "ABS", "AVG", "CAST", "CEIL", "CEILING", "CHAR_LENGTH", "COALESCE", "CONCAT", "COUNT",
    "CURRENT_TIMESTAMP", "DATE", "DATE_FORMAT", "DAY", "EXISTS", "FLOOR", "IF", "IFNULL", "IN",
    "JSON_EXTRACT", "JSON_UNQUOTE", "LEFT", "LENGTH", "LOWER", "MAX", "MIN", "MONTH", "NOW",
    "NULLIF", "REPLACE", "RIGHT", "ROUND", "SUBSTRING", "SUM", "TRIM", "UPPER", "YEAR",
}
_SELECT_GROUPING_KEYWORDS = {
    "ALL", "AND", "AS", "BY", "CASE", "DISTINCT", "ELSE", "EXCEPT", "FROM", "HAVING",
    "INTERSECT", "JOIN", "NOT", "ON", "OR", "OVER", "PARTITION", "SELECT", "THEN",
    "UNION", "USING", "WHEN", "WHERE",
}


def active_profile():
    return _ACTIVE_PROFILE


def validate_profile_name(profile):
    if not isinstance(profile, str) or not _PROFILE_NAME.fullmatch(profile):
        raise ValueError("profile 必须以字母开头，且只能包含字母、数字、- 或 _。")
    return profile


def set_active_profile(profile):
    global _ACTIVE_PROFILE
    _ACTIVE_PROFILE = validate_profile_name(profile) if profile else "default"


def load_config(profile=None):
    try:
        import yaml
    except ImportError as error:
        raise ImportError("缺少 pyyaml；请执行 python3 -m pip install -r requirements.lock。") from error
    if not CONFIG_PATH.exists():
        raise ValueError("本地配置不存在：{}；请从仓库 config/settings.yaml.example 创建。".format(CONFIG_PATH))
    if CONFIG_PATH.stat().st_mode & 0o077:
        raise ValueError("本地配置权限过宽：{}；请执行 chmod 600 {}。".format(CONFIG_PATH, CONFIG_PATH))
    try:
        with CONFIG_PATH.open(encoding="utf-8") as file:
            config = yaml.safe_load(file) or {}
    except yaml.YAMLError as error:
        raise ValueError("本地配置文件格式无效。") from error
    if not isinstance(config, dict):
        raise ValueError("本地配置文件必须是对象。")
    if "profiles" not in config:
        name = validate_profile_name(profile or active_profile())
        if name != "default":
            raise ValueError("未配置 profile：{}。".format(name))
        return config
    profiles = config["profiles"]
    if not isinstance(profiles, dict):
        raise ValueError("profiles 必须是 profile 名称到配置对象的映射。")
    for name in profiles:
        validate_profile_name(name)
    name = profile or active_profile()
    validate_profile_name(name)
    if name not in profiles or not isinstance(profiles[name], dict):
        raise ValueError("未配置 profile：{}。".format(name))
    return profiles[name]


def _keychain_value(account, profile=None):
    if platform.system() != "Darwin":
        return ""
    keychain_profile = validate_profile_name(profile) if profile else active_profile()
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", keychain_profile + "-" + account, "-w"],
            capture_output=True,
            text=True,
            timeout=KEYCHAIN_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _configured_secret(config, section, field):
    value = config.get(section, {}).get(field)
    return value.strip() if isinstance(value, str) else ""


def get_cookie(profile=None, config=None):
    name = profile or active_profile()
    return _keychain_value("paas-cookie", name) or _configured_secret(
        config if config is not None else {}, "paas", "cookie")


def get_test_db_password(profile=None, config=None):
    name = profile or active_profile()
    return _keychain_value("test-db-password", name) or _configured_secret(
        config if config is not None else {}, "test_db", "password")


def is_mysql_line_comment(sql, index):
    return (sql[index:index + 2] == "--" and index + 2 < len(sql)
            and ord(sql[index + 2]) <= 0x20)


def redact_text(value, patterns=()):
    """Mask common credential assignments before log data leaves the local tool chain."""
    result = _SENSITIVE_LOG_VALUE.sub(r"\1***", str(value))
    for pattern in patterns:
        result = re.sub(pattern, "***", result)
    return result


def log_analysis_rules(config):
    """Validate and compile optional private log-analysis rules once for every log path."""
    analysis = config.get("log_analysis", {})
    if not isinstance(analysis, dict):
        raise ValueError("log_analysis 必须是对象。")
    related = analysis.get("related_service_pattern", "")
    entities = analysis.get("entity_patterns", {})
    redaction = analysis.get("redaction_patterns", [])
    if not isinstance(related, str):
        raise ValueError("log_analysis.related_service_pattern 必须是正则字符串。")
    if not isinstance(entities, dict) or not all(isinstance(pattern, str) for pattern in entities.values()):
        raise ValueError("log_analysis.entity_patterns 必须是名称到正则字符串的映射。")
    if not isinstance(redaction, list) or not all(isinstance(pattern, str) for pattern in redaction):
        raise ValueError("log_analysis.redaction_patterns 必须是正则字符串列表。")
    try:
        if related:
            re.compile(related)
        for name, pattern in entities.items():
            re.compile(pattern)
        compiled_redaction = tuple(re.compile(pattern) for pattern in redaction)
    except re.error as error:
        if related:
            try:
                re.compile(related)
            except re.error:
                raise ValueError("log_analysis.related_service_pattern 包含无效正则。") from error
        for name, pattern in entities.items():
            try:
                re.compile(pattern)
            except re.error:
                raise ValueError("log_analysis.entity_patterns.{} 包含无效正则。".format(name)) from error
        raise ValueError("log_analysis.redaction_patterns 包含无效正则。") from error
    return {"related_service_pattern": related, "entity_patterns": entities,
            "redaction_patterns": compiled_redaction}


def redact_log_fields(value, patterns=()):
    """Recursively mask sensitive log fields while preserving non-sensitive structure."""
    if isinstance(value, dict):
        return {key: "***" if str(key).lower().replace("-", "_") in _SENSITIVE_LOG_KEYS
                else redact_log_fields(item, patterns) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_log_fields(item, patterns) for item in value]
    return redact_text(value, patterns) if isinstance(value, str) else value


def api_headers(config, cookie):
    paas_config = config.get("paas", {})
    prefix = paas_config.get("cookie_prefix", "")
    headers = {"accept": "application/json", "content-type": "application/json"}
    headers.update(paas_config.get("request_headers", {}))
    headers["cookie"] = cookie if not prefix or cookie.startswith(prefix) else prefix + cookie
    return headers


def query_configuration_errors(config, environments=("prod", "test")):
    """Return the missing PaaS query settings required for a readiness check."""
    paas_config = config.get("paas", {})
    errors = []
    if not paas_config.get("query_api_url"):
        errors.append("PaaS 查询端点未配置。")
    fields = paas_config.get("query_contract", {}).get("fields", {})
    if any(not fields.get(name) for name in ("group", "env", "sql", "limit")):
        errors.append("PaaS query_contract 未配置完整字段。")
    missing_environments = [name for name in environments
                            if not paas_config.get("query_envs", {}).get(name)]
    if missing_environments:
        errors.append("PaaS 查询环境映射未配置：{}。".format("、".join(missing_environments)))
    return errors


def test_database_configuration_errors(config, service=None):
    test_db = config.get("test_db", {})
    errors = []
    if not test_db.get("host"):
        errors.append("测试库 host 未配置。")
    if not test_db.get("user"):
        errors.append("测试库 user 未配置。")
    if service:
        services = config.get("services", {})
        service_config = services.get(service) if isinstance(services, dict) else None
        if not isinstance(service_config, dict) or not service_config.get("test_database"):
            errors.append("服务未配置测试数据库：{}。".format(service))
    return errors


def apply_configuration_errors(config, environments=("prod", "test")):
    paas_config = config.get("paas", {})
    errors = []
    if (not paas_config.get("apply_api_base") or not paas_config.get("apply_response_id_field")
            or any(not paas_config.get("apply_endpoints", {}).get(kind) for kind in ("ddl", "dml"))):
        errors.append("PaaS apply 提交端点或响应标识字段未配置。")
    missing_environments = [name for name in environments
                            if not paas_config.get("apply_envs", {}).get(name)]
    if missing_environments:
        errors.append("PaaS apply 环境映射未配置：{}。".format("、".join(missing_environments)))
    fields = paas_config.get("apply_contract", {}).get("fields", {})
    required = ("sql", "service", "group", "reason", "envs")
    if (not paas_config.get("apply_contract", {}).get("service_name")
            or any(not fields.get(name) for name in required)):
        errors.append("PaaS apply_contract 未配置完整字段。")
    if ("prod" in environments and all(fields.get(name) for name in required)
            and any(not fields.get(name) for name in ("start", "end"))):
        errors.append("PaaS apply_contract 未配置执行窗口字段。")
    actions = paas_config.get("task_actions", {})
    if (not paas_config.get("task_api_base") or not isinstance(actions, dict)
            or any(not isinstance(actions.get(name), dict)
                   or not actions[name].get("endpoint") or not actions[name].get("id_field")
                   for name in ("approve", "execute", "recall"))):
        errors.append("PaaS 工单操作端点或字段未配置。")
    return errors


def _sql_code(sql, preserve_backtick_identifiers=False):
    """剥离字符串和注释，供 SQL 安全校验使用。"""
    result, index, quote = [], 0, None
    while index < len(sql):
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < len(sql) else ""
        if quote:
            preserve = quote == "`" and preserve_backtick_identifiers
            result.append(char if preserve else " ")
            if char == "\\" and next_char:
                result.append(next_char if preserve else " ")
                index += 2
                continue
            if char == quote:
                if next_char == quote:
                    result.append(next_char if preserve else " ")
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if char in ("'", '"', "`"):
            quote = char
            result.append(char if char == "`" and preserve_backtick_identifiers else " ")
            index += 1
            continue
        if char == "/" and next_char == "*":
            if index + 2 < len(sql) and sql[index + 2] == "!":
                return ""
            end = sql.find("*/", index + 2)
            if end < 0:
                return ""
            result.extend(" " * (end + 2 - index))
            index = end + 2
            continue
        if is_mysql_line_comment(sql, index) or char == "#":
            end = sql.find("\n", index)
            end = len(sql) if end < 0 else end
            result.extend(" " * (end - index))
            index = end
            continue
        result.append(char)
        index += 1
    return "" if quote else "".join(result)


def is_read_only_select(sql):
    code = _sql_code(sql).strip()
    if code.endswith(";"):
        code = code[:-1].rstrip()
    if not code or ";" in code or not re.match(r"SELECT\b", code, re.IGNORECASE):
        return False
    tokens = re.findall(r"[A-Z_]+", code.upper())
    pairs = set(zip(tokens, tokens[1:]))
    if pairs & {("INTO", "OUTFILE"), ("INTO", "DUMPFILE"), ("FOR", "UPDATE"), ("FOR", "SHARE")}:
        return False
    function_code = _sql_code(sql, preserve_backtick_identifiers=True).upper()
    for match in re.finditer(r"(?<![\w$])([\w$]+)\s*\(|`([^`]+)`\s*\(", function_code):
        name = match.group(1)
        if (name not in _SAFE_SELECT_FUNCTIONS and name not in _SELECT_GROUPING_KEYWORDS
                or match.group(2)
                or function_code[:match.start()].rstrip().endswith(".")):
            return False
    if re.search(r"\bINTO\s+@|@\s*[A-Z0-9_$]*\s*:=", code.upper()):
        return False
    return not any(tokens[index:index + 4] == ["LOCK", "IN", "SHARE", "MODE"]
                   for index in range(len(tokens) - 3))


def select_limit(sql):
    """Return a simple numeric SELECT LIMIT, or None when it is absent or complex."""
    code = _sql_code(sql).strip().rstrip(";").rstrip()
    match = re.search(r"\bLIMIT\s+(\d+)\s*$", code, re.IGNORECASE)
    return int(match.group(1)) if match else None


def has_wildcard_projection(sql):
    """Detect a standalone wildcard in every SELECT list, including subqueries."""
    code = _sql_code(sql)
    modifiers = (r"ALL|DISTINCT|DISTINCTROW|HIGH_PRIORITY|STRAIGHT_JOIN|SQL_SMALL_RESULT|"
                 r"SQL_BIG_RESULT|SQL_BUFFER_RESULT|SQL_NO_CACHE|SQL_CALC_FOUND_ROWS")
    for select in re.finditer(r"\bSELECT\b", code, re.IGNORECASE):
        depth, end = 0, len(code)
        for boundary in re.finditer(r"\b(?:FROM|LIMIT|UNION)\b|[()]", code[select.end():], re.IGNORECASE):
            token = boundary.group().upper()
            if token == "(":
                depth += 1
            elif token == ")":
                if depth == 0:
                    end = select.end() + boundary.start()
                    break
                depth -= 1
            elif depth == 0:
                end = select.end() + boundary.start()
                break
        projection = re.sub(r"^\s*(?:(?:{})\s+)*".format(modifiers), "", code[select.end():end],
                            flags=re.IGNORECASE)
        if re.search(r"(^|,)\s*(?:(?:\w+\s*)?\.\s*)*\*\s*(?=,|$)", projection):
            return True
    return False


def build_session():
    import requests
    from requests.adapters import HTTPAdapter

    class TLSAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            kwargs["ssl_context"] = context
            return super().init_poolmanager(*args, **kwargs)

    session = requests.Session()
    session.trust_env = False
    session.mount("https://", TLSAdapter())
    return session


def service_group(config, service):
    details = config.get("services", {}).get(service)
    if not details or not details.get("prod_db_group"):
        raise ValueError("服务未配置生产数据库组：{}".format(service))
    return details["prod_db_group"]


def query_payload(config, service, env, sql, limit):
    paas_config = config.get("paas", {})
    fields = paas_config.get("query_contract", {}).get("fields", {})
    required = ("group", "env", "sql", "limit")
    if any(not fields.get(name) for name in required):
        raise ValueError("PaaS query_contract 未配置完整字段。")
    paas_env = paas_config.get("query_envs", {}).get(env)
    if not paas_env:
        raise ValueError("PaaS 查询端点或 {} 环境映射未配置。".format(env))
    return {fields["group"]: service_group(config, service), fields["env"]: paas_env,
            fields["sql"]: sql, fields["limit"]: limit}


def query(config, service, env, sql, limit=1000):
    """Execute the documented fixed PaaS result envelope: [{columnList, rows}]."""
    import requests

    cookie = get_cookie(config=config)
    if not cookie:
        raise ValueError("未找到 PaaS Cookie；请写入 macOS Keychain 或私有配置文件。")
    paas_config = config.get("paas", {})
    url = paas_config.get("query_api_url", "")
    if not url:
        raise ValueError("PaaS 查询端点未配置。")
    headers = api_headers(config, cookie)
    payload = query_payload(config, service, env, sql, limit)
    try:
        response = build_session().post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return {"error": "PaaS 查询请求失败。"}
    except ValueError:
        return {"error": "PaaS 查询返回了非 JSON 响应。"}
    if isinstance(data, dict) and data.get("error"):
        return {"error": "PaaS 查询被拒绝。"}
    if not isinstance(data, list):
        return {"error": "PaaS 查询返回结构无效。"}
    if len(data) != 1:
        return {"error": "PaaS 查询返回结构无效。"}
    first = data[0]
    if not isinstance(first, dict) or "columnList" not in first or "rows" not in first:
        return {"error": "PaaS 查询返回结构无效。"}
    columns, rows = first.get("columnList", []), first.get("rows", [])
    if (not isinstance(columns, list) or not all(isinstance(column, str) for column in columns)
            or not isinstance(rows, list) or len(rows) > limit
            or any(not isinstance(row, list) or len(row) != len(columns) for row in rows)):
        return {"error": "PaaS 查询返回结构无效。"}
    return {"columns": columns, "rows": rows}


def print_json(value, stream=None):
    print(json.dumps(value, ensure_ascii=False, indent=2), file=stream)
