#!/usr/bin/env python3
"""Copy this skill into an installed directory without deleting local files."""
import shutil
import sys
from pathlib import Path


def sync_skill(destination):
    source = Path(__file__).resolve().parent.parent
    destination = Path(destination).expanduser().resolve()
    if destination == source:
        raise ValueError("同步目标不能是源码目录。")
    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", ".code-review-graph", "__pycache__", ".pdlc-state"),
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("用法：sync_skill.py <目标目录>")
    try:
        sync_skill(sys.argv[1])
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(2)
