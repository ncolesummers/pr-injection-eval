#!/usr/bin/env bash
# Full runs: every sample, both conditions, 5 epochs, on each model.
# This costs real money. Check the estimate from the pilot first:
#
#     uv run python scripts/summarize.py <pilot log dir>
#
# Usage: scripts/full_runs.sh [model ...]   (default: the small and strong models)
#        EPOCHS=3 scripts/full_runs.sh      (fewer epochs)
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/common.sh

if [[ $# -gt 0 ]]; then models=("$@"); else models=("$SMALL_MODEL" "$STRONG_MODEL"); fi
epochs="${EPOCHS:-5}"
# One directory per launch, so a rerun never mixes with an earlier run.
log_dir="logs/$(date +%Y-%m-%d-%H%M)"

for model in "${models[@]}"; do
    for defended in false true; do
        run_eval --model "$model" -T defended="$defended" \
            --epochs "$epochs" --log-dir "$log_dir" --display plain
    done
done

echo
echo "Logs: $log_dir"
echo "Summary: uv run python scripts/summarize.py $log_dir"
