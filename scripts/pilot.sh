#!/usr/bin/env bash
# Pilot: the demo slice, both conditions, 2 epochs, on each model.
# Small and cheap. Its token usage is what the full-run cost estimate uses.
#
# Usage: scripts/pilot.sh [model ...]     (default: the small and strong models)
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/common.sh

if [[ $# -gt 0 ]]; then models=("$@"); else models=("$SMALL_MODEL" "$STRONG_MODEL"); fi
log_dir="logs/pilot-$(date +%Y-%m-%d-%H%M)"

for model in "${models[@]}"; do
    for defended in false true; do
        run_eval --model "$model" -T demo=true -T defended="$defended" \
            --epochs 2 --log-dir "$log_dir" --display plain
    done
done

echo
echo "Logs: $log_dir"
echo "Summary: uv run python scripts/summarize.py $log_dir"
