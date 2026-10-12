#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CAPABILITY="all"

if [[ $# -eq 2 && $1 == "--capability" ]]; then
  CAPABILITY="$2"
elif [[ $# -ne 0 ]]; then
  echo "用法：$0 [--capability <all|paas|sls|db|export|apply>]" >&2
  exit 2
fi

case "$CAPABILITY" in
  all|paas|sls|db|export|apply) ;;
  *)
    echo "用法：$0 [--capability <all|paas|sls|db|export|apply>]" >&2
    exit 2
    ;;
esac

if ! python3 "$SKILL_DIR/scripts/setup.py" --check-dependencies --capability "$CAPABILITY"; then
  echo "缺少依赖，请自行执行：python3 -m pip install -r $SKILL_DIR/requirements.lock" >&2
  exit 1
fi

CONFIG_DIR="$HOME/.service-ops"
CONFIG_FILE="$CONFIG_DIR/config.yaml"
if [[ ! -f "$CONFIG_FILE" ]]; then
  mkdir -p -m 700 "$CONFIG_DIR"
  chmod 700 "$CONFIG_DIR"
  cp "$SKILL_DIR/config/settings.yaml.example" "$CONFIG_FILE"
  chmod 600 "$CONFIG_FILE"
  echo "已创建 $CONFIG_FILE；请填写后重试。" >&2
  exit 1
fi

python3 "$SKILL_DIR/scripts/setup.py" --check --capability "$CAPABILITY"
echo "依赖、配置和凭据已就绪（${CAPABILITY}）。"
