# Shared by pilot.sh, full_runs.sh, and demo_live.sh. Source it, do not run it.

# Default models live here and nowhere else. Override with environment
# variables, or pass model names as arguments to the scripts.
SMALL_MODEL="${SMALL_MODEL:-anthropic/claude-haiku-5-5}"
STRONG_MODEL="${STRONG_MODEL:-anthropic/claude-sonnet-5-5}"
# The live demo uses the model that most often followed planted instructions
# in the full runs, so there is something to look at on screen.
DEMO_MODEL="${DEMO_MODEL:-google/gemini-3.1-flash-lite}"

TASK="src/pr_injection_eval/task.py"

# Run `inspect eval` on the task with the given extra arguments.
#
# API keys come from 1Password: `op run` resolves the secret references in
# op.env and passes the keys to Inspect as environment variables. They are
# never written to disk. Without an op.env file, this falls back to whatever
# keys are already set in the environment.
run_eval() {
    if [[ -f op.env ]]; then
        op run --env-file=op.env -- uv run inspect eval "$TASK" "$@"
    elif [[ -n "${ANTHROPIC_API_KEY:-}${OPENAI_API_KEY:-}${GOOGLE_API_KEY:-}" ]]; then
        uv run inspect eval "$TASK" "$@"
    else
        echo "No op.env file and no API key in the environment. See the README." >&2
        return 1
    fi
}
