#!/usr/bin/env python3
"""将已配置服务的只读查询结果导出为 Excel。"""
import argparse
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

import paas


MAX_EXPORT_ROWS = 10000
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def is_export_query(sql):
    limit = paas.select_limit(sql)
    return paas.is_read_only_select(sql) and limit is not None and limit <= MAX_EXPORT_ROWS


def read_sql(sql, sql_file):
    if sql_file:
        return Path(sql_file).read_text(encoding="utf-8").strip()
    if sql == "-":
        return sys.stdin.read().strip()
    return (sql or "").strip()


def is_valid_output_path(output):
    return output.is_absolute() and output.suffix.lower() == ".xlsx"


def safe_excel_value(value):
    return "'" + value if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES) else value


def validate_export_result(columns, rows, limit):
    if len(rows) > limit:
        raise ValueError("PaaS 查询返回行数超过已批准的 LIMIT。")
    if any(not isinstance(row, (list, tuple)) or len(row) != len(columns) for row in rows):
        raise ValueError("PaaS 查询返回行结构无效。")


def write_xlsx(columns, rows, output):
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append([safe_excel_value(value) for value in columns])
    for row in rows:
        sheet.append([safe_excel_value(value) for value in row])
    temporary = None
    try:
        with NamedTemporaryFile(dir=output.parent, suffix=output.suffix, delete=False) as file:
            temporary = Path(file.name)
        workbook.save(temporary)
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="导出只读查询结果为 Excel")
    parser.add_argument("--env", required=True, choices=["prod", "test"])
    parser.add_argument("--service", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--sql")
    source.add_argument("--sql-file")
    parser.add_argument("--output", required=True, help="目标绝对 .xlsx 文件")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--profile")
    args = parser.parse_args()
    try:
        paas.set_active_profile(args.profile)
    except ValueError as error:
        parser.error(str(error))
    try:
        args.sql = read_sql(args.sql, args.sql_file)
    except (OSError, UnicodeError):
        parser.error("读取 SQL 文件失败。")
    if not is_export_query(args.sql):
        parser.error("导出仅允许带不超过 {} 行 LIMIT 的单条非锁定 SELECT。".format(MAX_EXPORT_ROWS))
    limit = paas.select_limit(args.sql)
    output = Path(args.output).expanduser()
    if not is_valid_output_path(output):
        parser.error("导出文件必须是绝对 .xlsx 路径。")
    if output.exists() and not args.overwrite:
        parser.error("输出文件已存在；确认覆盖后传 --overwrite。")
    try:
        result = paas.query(paas.load_config(), args.service, args.env, args.sql, limit)
    except (OSError, ValueError, ImportError) as error:
        paas.print_json({"error": str(error)}, stream=sys.stderr)
        raise SystemExit(2)
    if result.get("error"):
        paas.print_json(result, stream=sys.stderr)
        raise SystemExit(2)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        validate_export_result(result["columns"], result["rows"], limit)
        rows = write_xlsx(result["columns"], result["rows"], output)
    except ImportError:
        parser.error("缺少 openpyxl；请安装 requirements.txt。")
    except ValueError as error:
        paas.print_json({"error": str(error)}, stream=sys.stderr)
        raise SystemExit(2)
    except OSError:
        paas.print_json({"error": "Excel 文件写入失败。"}, stream=sys.stderr)
        raise SystemExit(2)
    paas.print_json({"output": str(output), "rows": rows})


if __name__ == "__main__":
    main()
