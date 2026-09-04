#!/usr/bin/env python3
"""初始化 service-ops 的用户私有配置，并检查凭据是否就绪。"""
import argparse
import importlib.util
import shutil
from pathlib import Path

import paas
import sls_query


REQUIRED_MODULES = {
    "requests": "requests",
    "yaml": "pyyaml",
    "aliyun.log": "aliyun-log-python-sdk",
    "openpyxl": "openpyxl",
    "pymysql": "pymysql",
}
CAPABILITY_MODULES = {
    "paas": ("requests", "yaml"),
    "sls": ("yaml", "aliyun.log"),
    "db": ("yaml", "pymysql"),
    "export": ("requests", "yaml", "openpyxl"),
    "apply": ("requests", "yaml"),
}


def missing_dependencies(capability="all"):
    modules = REQUIRED_MODULES if capability == "all" else CAPABILITY_MODULES[capability]
    missing = []
    for module in modules:
        package = REQUIRED_MODULES[module]
        try:
            available = importlib.util.find_spec(module) is not None
        except ModuleNotFoundError:
            available = False
        if not available:
            missing.append(package)
    return missing


def check_readiness(capability="all", profile=None, service=None):
    missing = missing_dependencies(capability)
    errors = ["缺少 Python 依赖：{}".format(", ".join(missing))] if missing else []
    config = None
    if "pyyaml" not in missing:
        try:
            config = paas.load_config(profile)
        except (ImportError, ValueError) as error:
            errors.append(str(error))
    if capability in ("all", "paas", "export", "apply") and not paas.get_cookie(profile, config):
        errors.append("PaaS Cookie 未配置")
    if capability in ("all", "paas", "export") and config is not None:
        errors.extend(paas.query_configuration_errors(config))
    if capability in ("all", "db") and config is not None:
        database_errors = paas.test_database_configuration_errors(config, service)
        errors.extend(database_errors)
        if not database_errors and not paas.get_test_db_password(profile, config):
            errors.append("测试库密码未配置。")
    if capability in ("all", "apply") and config is not None:
        errors.extend(paas.apply_configuration_errors(config))
    if capability in ("all", "sls") and config is not None:
        try:
            paas.log_analysis_rules(config)
        except ValueError as error:
            errors.append(str(error))
        settings = config.get("sls", {})
        if not settings.get("project"):
            errors.append("当前 profile 未配置 SLS project。")
        if not settings.get("region") and not settings.get("endpoint"):
            errors.append("当前 profile 未配置 SLS region 或 endpoint。")
        try:
            sls_query.get_credentials(profile, config)
        except ValueError as error:
            errors.append(str(error))
    return errors


def main():
    parser = argparse.ArgumentParser(description="service-ops 本地配置初始化")
    parser.add_argument("--init", action="store_true", help="创建 ~/.service-ops/config.yaml")
    parser.add_argument("--check", action="store_true", help="检查配置权限与 Keychain 凭据")
    parser.add_argument("--capability", choices=("all", "paas", "sls", "db", "export", "apply"), default="all",
                        help="--check 的检查范围，默认 all")
    parser.add_argument("--profile", help="要检查的配置 profile，默认 default")
    parser.add_argument("--service", help="检查 db 时一并校验该服务的 test_database 映射")
    parser.add_argument("--check-dependencies", action="store_true", help="仅检查 Python 运行依赖")
    args = parser.parse_args()
    config = paas.CONFIG_PATH
    if args.init:
        config.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        config.parent.chmod(0o700)
        if not config.exists():
            shutil.copyfile(Path(__file__).parent.parent / "config" / "settings.yaml.example", config)
            config.chmod(0o600)
            print("已创建 {}；请填写真实配置。".format(config))
        else:
            print("配置已存在：{}".format(config))
        return
    if args.check_dependencies:
        missing = missing_dependencies(args.capability)
        if missing:
            print("缺少 Python 依赖：{}".format(", ".join(missing)))
            raise SystemExit(2)
        print("Python 运行依赖：OK")
        return
    if not args.check:
        parser.error("请指定 --init、--check 或 --check-dependencies。")
    if args.service and args.capability not in ("all", "db"):
        parser.error("--service 仅能与 --capability db 或 all 一起使用。")
    errors = check_readiness(args.capability, args.profile, args.service)
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(2)
    print("配置与凭据：OK ({}, {})".format(config, args.capability))


if __name__ == "__main__":
    main()
