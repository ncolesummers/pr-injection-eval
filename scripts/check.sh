#!/usr/bin/env bash
# The full check: formatting, lint, types, tests. No API key is needed,
# because no test calls a model. Run this before every commit.
set -euo pipefail
cd "$(dirname "$0")/.."

uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest -q

# House rule: no em dashes anywhere in the repo (model-written logs excepted).
# The character is built from its UTF-8 bytes so this file passes its own check.
em_dash="$(printf '\342\200\224')"
if git grep -n "$em_dash" -- . ':!logs' ':!uv.lock'; then
    echo "Found an em dash. Please reword." >&2
    exit 1
fi

# Nothing that looks like an API key may be tracked, including in logs.
if git grep -nE 'sk-(ant|proj)-[A-Za-z0-9_-]{8,}' -- .; then
    echo "Found something that looks like an API key." >&2
    exit 1
fi

echo "All checks passed."
