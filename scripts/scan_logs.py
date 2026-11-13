"""Scan Inspect logs for anything that should not be published.

Usage:
    uv run python scripts/scan_logs.py logs/2026-11-13-1301

Run this before committing logs. Inspect logs are compressed archives, so a
plain text search (including the one in check.sh) cannot see inside them.
This reads each log in full and searches all of it.

API keys and 1Password references fail the scan. Local file paths are
reported but do not fail it: Inspect records them in error tracebacks.
"""

import re
import sys

from inspect_ai.log import list_eval_logs, read_eval_log

SECRETS = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{8,}|sk-proj-[A-Za-z0-9_-]{8,}|AIza[0-9A-Za-z_-]{30,}|op://"
)
LOCAL_PATHS = re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+")


def main() -> None:
    failed = False
    for info in list_eval_logs(sys.argv[1]):
        text = read_eval_log(info).model_dump_json()
        secrets = len(SECRETS.findall(text))
        homes = sorted(set(LOCAL_PATHS.findall(text)))
        print(f"{info.name.split('/')[-1]}: {secrets} secrets, home paths: {homes}")
        failed = failed or secrets > 0
    if failed:
        raise SystemExit("Found something that looks like a secret. Do not commit.")


if __name__ == "__main__":
    main()
