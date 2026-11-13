#!/usr/bin/env bash
# The live demo: 13 samples (11 attacks, 2 clean), baseline prompt, one model.
# Takes about 20 seconds.
#
# Usage: scripts/demo_live.sh                 baseline
#        scripts/demo_live.sh true            with the defense
#        scripts/demo_live.sh false <model>   a different model
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/common.sh

defended="${1:-false}"
model="${2:-$DEMO_MODEL}"

run_eval --model "$model" -T demo=true -T defended="$defended" \
    --log-dir "logs/demo-$(date +%Y-%m-%d)"
