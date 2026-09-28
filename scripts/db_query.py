#!/usr/bin/env python3
"""排障数据库查询：生产走 PaaS，测试走 MySQL，均只允许只读 SELECT。"""
import argparse
import sys

import paas


MAX_INCIDENT_ROWS = 100


def is_incident_query(sql):
    limit = paas.select_limit(sql)
    return (paas.is_read_only_select(sql) and not paas.has_wildcard_projection(sql)
            and limit is not None and limit <= MAX_INCIDENT_ROWS)


def query_prod(sql, service, config):
    return paas.query(config, service, "prod", sql, paas.select_limit(sql))


def query_test(sql, database, config):
    if not database:
        raise ValueError("服务未配置测试数据库。")
    test_db = config.get("test_db", {})
    if not test_db.get("host"):
        raise ValueError("测试库 host 未配置。")
    password = paas.get_test_db_password(config=config)
    if not password:
        raise ValueError("未找到测试库密码。")
    if not test_db.get("user"):
        raise ValueError("测试库 user 未配置。")
    import pymysql
    try:
        connection = pymysql.connect(host=test_db["host"], port=test_db.get("port", 3306),
                                     user=test_db["user"], password=password,
                                     database=database, charset="utf8mb4", connect_timeout=10, read_timeout=30)
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                return {"columns": [column[0] for column in cursor.description], "rows": [list(row) for row in cursor.fetchall()]}
        finally:
            connection.close()
    except pymysql.MySQLError as error:
        raise ValueError("测试库查询失败。") from error


def main():
    parser = argparse.ArgumentParser(description="排障只读数据库查询")
    parser.add_argument("--env", required=True, choices=["prod", "test"])
    parser.add_argument("--service", required=True)
    parser.add_argument("--purpose", required=True)
    parser.add_argument("--sql", required=True)
    parser.add_argument("--profile")
    args = parser.parse_args()
    try:
        paas.set_active_profile(args.profile)
    except ValueError as error:
        parser.error(str(error))
    args.purpose = args.purpose.strip()
    if not args.purpose:
        parser.error("--purpose 不能为空。")
    if not is_incident_query(args.sql):
        parser.error("仅允许显式字段、带不超过 {} 行 LIMIT 的单条非锁定 SELECT。".format(MAX_INCIDENT_ROWS))
    try:
        config = paas.load_config()
        service = config.get("services", {}).get(args.service)
        if not service:
            raise ValueError("未配置服务：{}".format(args.service))
        result = query_prod(args.sql, args.service, config) if args.env == "prod" else query_test(args.sql, service.get("test_database", ""), config)
    except (ImportError, OSError, ValueError) as error:
        paas.print_json({"error": str(error)}, stream=sys.stderr)
        raise SystemExit(2)
    if result.get("error"):
        paas.print_json(result, stream=sys.stderr)
        raise SystemExit(2)
    paas.print_json({"purpose": args.purpose, **result})


if __name__ == "__main__":
    main()
