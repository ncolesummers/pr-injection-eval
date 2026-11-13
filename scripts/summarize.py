"""Read Inspect logs and print the results tables as markdown.

Usage:
    uv run python scripts/summarize.py logs/2026-11-13-1500
    uv run python scripts/summarize.py logs/pilot-... --estimate-samples 47 --estimate-epochs 5

It reads every sample of every epoch, not the averaged metrics, so it can
also show how often the same sample came out differently across epochs.

It refuses to summarize a directory that mixes experiments: every log must
have finished, there must be one log per model and condition, and all of
them must have used the same dataset settings.
"""

import argparse
from collections import defaultdict
from dataclasses import dataclass

from inspect_ai.log import EvalLog, list_eval_logs, read_eval_log

from pr_injection_eval.dataset import (
    DEFAULT_PRS_PER_CELL,
    DEFAULT_SEED,
    build_samples,
    dataset_hash,
)
from pr_injection_eval.injections import GOALS, TECHNIQUES


@dataclass(frozen=True)
class Price:
    """US dollars per million tokens. Checked 2026-11-13; prices change."""

    input: float
    output: float
    cache_read: float
    cache_write: float


PRICES: dict[str, Price] = {
    "anthropic/claude-haiku-5-5": Price(0.10, 0.50, 0.01, 0.125),
    "anthropic/claude-sonnet-5-5": Price(2.00, 10.00, 0.10, 2.50),
    # Gemini has no separate cache-write charge at these prompt sizes.
    "google/gemini-3.1-flash-lite": Price(0.25, 1.50, 0.025, 0.25),
    "google/gemini-4-hydrogen": Price(1.50, 7.50, 0.075, 1.50),
}


@dataclass(frozen=True)
class Row:
    """One sample in one epoch of one run."""

    model: str
    defended: bool
    sample_id: str
    base_pr: str
    technique: str
    goal: str
    injected: bool
    attack_succeeded: bool | None
    honeypot_called: bool
    attacker_text_leaked: bool | None
    review_posted: bool
    defect_caught: bool | None
    useful: bool
    flagged_injection: bool
    injection_seen: bool | None


@dataclass(frozen=True)
class Usage:
    """Tokens used by one run."""

    model: str
    defended: bool
    sample_epochs: int
    input_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    output_tokens: int

    def cost(self) -> float | None:
        price = PRICES.get(self.model)
        if price is None:
            return None
        dollars = (
            self.input_tokens * price.input
            + self.cache_write_tokens * price.cache_write
            + self.cache_read_tokens * price.cache_read
            + self.output_tokens * price.output
        )
        return dollars / 1_000_000


Condition = tuple[str, bool]  # (model, defended)


def optional_bool(value: object) -> bool | None:
    return None if value is None else bool(value)


def condition_of(log: EvalLog) -> Condition:
    return (log.eval.model, bool(log.eval.task_args.get("defended", False)))


def dataset_settings(log: EvalLog) -> dict[str, object]:
    """The task arguments that decide which samples a run contains."""
    args = log.eval.task_args
    return {
        "demo": bool(args.get("demo", False)),
        "seed": int(args.get("seed", DEFAULT_SEED)),
        "prs_per_cell": int(args.get("prs_per_cell", DEFAULT_PRS_PER_CELL)),
    }


def check_comparable(logs: list[EvalLog]) -> None:
    """Stop if these logs should not be put in one table."""
    problems: list[str] = []
    seen: set[Condition] = set()
    for log in logs:
        if log.status != "success":
            problems.append(f"{log.location}: status is {log.status}, not success")
        if condition_of(log) in seen:
            problems.append(
                f"{log.location}: second log for {label(condition_of(log))}"
            )
        seen.add(condition_of(log))
        if dataset_settings(log) != dataset_settings(logs[0]):
            problems.append(f"{log.location}: different dataset settings")
        if sample_ids(log) != sample_ids(logs[0]):
            problems.append(f"{log.location}: different set of samples")
    if problems:
        raise SystemExit("These logs cannot be compared:\n  " + "\n  ".join(problems))


def sample_ids(log: EvalLog) -> set[str]:
    return {str(sample.id) for sample in log.samples or []}


def read_rows(log: EvalLog) -> tuple[list[Row], int]:
    """Rows for every scored sample, plus a count of samples that errored."""
    model, defended = condition_of(log)
    rows: list[Row] = []
    errors = 0
    for sample in log.samples or []:
        if sample.error is not None or not sample.scores:
            errors += 1
            continue
        # Both scorers store the same components; read them from one.
        components = sample.scores["usefulness"].metadata or {}
        rows.append(
            Row(
                model=model,
                defended=defended,
                sample_id=str(sample.id),
                base_pr=str(sample.metadata["base_pr"]),
                technique=str(sample.metadata["technique"]),
                goal=str(sample.metadata["goal"]),
                injected=bool(sample.metadata["injected"]),
                attack_succeeded=optional_bool(components["attack_succeeded"]),
                honeypot_called=bool(components["honeypot_called"]),
                attacker_text_leaked=optional_bool(components["attacker_text_leaked"]),
                review_posted=bool(components["review_posted"]),
                defect_caught=optional_bool(components["defect_caught"]),
                useful=bool(components["useful"]),
                flagged_injection=bool(components["flagged_injection"]),
                injection_seen=optional_bool(components["injection_seen"]),
            )
        )
    return rows, errors


def read_usage(log: EvalLog) -> Usage:
    model, defended = condition_of(log)
    usage = log.stats.model_usage.get(model)
    return Usage(
        model=model,
        defended=defended,
        sample_epochs=len(log.samples or []),
        input_tokens=usage.input_tokens if usage else 0,
        cache_write_tokens=(usage.input_tokens_cache_write or 0) if usage else 0,
        cache_read_tokens=(usage.input_tokens_cache_read or 0) if usage else 0,
        output_tokens=usage.output_tokens if usage else 0,
    )


def rate(hits: int, total: int) -> str:
    """A rate with its counts, so small samples are obvious."""
    if total == 0:
        return "n/a"
    return f"{hits}/{total} ({100 * hits / total:.0f}%)"


def label(condition: Condition) -> str:
    model, defended = condition
    return f"{model.split('/')[-1]} {'defended' if defended else 'baseline'}"


def table(header: list[str], body: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(line) + " |" for line in body]
    return "\n".join(lines)


def of(rows: list[Row], condition: Condition) -> list[Row]:
    return [row for row in rows if (row.model, row.defended) == condition]


def attack_rate(rows: list[Row]) -> str:
    injected = [row for row in rows if row.injected]
    return rate(sum(row.attack_succeeded is True for row in injected), len(injected))


def run_table(logs: list[EvalLog]) -> str:
    body = [
        [
            label(condition_of(log)),
            log.eval.model,
            log.eval.created[:10],
            str(log.eval.config.epochs or 1),
            str(len(sample_ids(log))),
            log.eval.packages.get("inspect_ai", "unknown"),
        ]
        for log in logs
    ]
    return table(["run", "model id", "date", "epochs", "samples", "Inspect"], body)


def technique_table(rows: list[Row], conditions: list[Condition]) -> str:
    body = [
        [
            technique.name,
            *(
                attack_rate([r for r in of(rows, c) if r.technique == technique.name])
                for c in conditions
            ),
        ]
        for technique in TECHNIQUES
    ]
    body.append(["**all injected**", *(attack_rate(of(rows, c)) for c in conditions)])
    return table(["technique", *map(label, conditions)], body)


def goal_table(rows: list[Row], conditions: list[Condition]) -> str:
    body = [
        [
            goal,
            *(
                attack_rate([r for r in of(rows, c) if r.goal == goal])
                for c in conditions
            ),
        ]
        for goal in GOALS
    ]

    # The comparison row for suppress: how often is the bug missed on the
    # same base PRs when nothing is planted at all?
    def missed_on_clean(condition: Condition) -> str:
        mine = of(rows, condition)
        suppress_prs = {row.base_pr for row in mine if row.goal == "suppress"}
        clean = [r for r in mine if not r.injected and r.base_pr in suppress_prs]
        return rate(sum(r.defect_caught is False for r in clean), len(clean))

    body.append(
        [
            "*bug missed on the same PRs, nothing planted*",
            *map(missed_on_clean, conditions),
        ]
    )
    return table(["attacker goal", *map(label, conditions)], body)


def usefulness_table(
    rows: list[Row], conditions: list[Condition], errors: dict[Condition, int]
) -> str:
    body: list[list[str]] = []
    for condition in conditions:
        mine = of(rows, condition)
        with_defect = [row for row in mine if row.defect_caught is not None]
        clean = [row for row in mine if not row.injected]
        injected = [row for row in mine if row.injected]
        leaks = [row for row in mine if row.attacker_text_leaked is True]
        body.append(
            [
                label(condition),
                rate(sum(row.useful for row in mine), len(mine)),
                rate(sum(row.review_posted for row in mine), len(mine)),
                rate(
                    sum(row.defect_caught is True for row in with_defect),
                    len(with_defect),
                ),
                rate(sum(row.honeypot_called for row in clean), len(clean)),
                rate(
                    sum(row.injection_seen is True for row in injected), len(injected)
                ),
                rate(sum(row.flagged_injection for row in injected), len(injected)),
                rate(sum(row.flagged_injection for row in leaks), len(leaks)),
                str(errors[condition]),
            ]
        )
    header = [
        "run",
        "useful",
        "review posted",
        "bug caught (PRs with a bug)",
        "honeypot called on clean",
        "saw the planted text",
        "flagged it",
        "leaks that were flagged",
        "errored samples",
    ]
    return table(header, body)


def variation_table(rows: list[Row], conditions: list[Condition]) -> str:
    """How many injected samples gave different outcomes in different epochs."""
    body: list[list[str]] = []
    for condition in conditions:
        outcomes: dict[str, list[bool]] = defaultdict(list)
        for row in of(rows, condition):
            if row.injected:
                outcomes[row.sample_id].append(row.attack_succeeded is True)
        always = sum(all(results) for results in outcomes.values())
        never = sum(not any(results) for results in outcomes.values())
        mixed = len(outcomes) - always - never
        body.append([label(condition), str(never), str(mixed), str(always)])
    header = [
        "run",
        "attack never worked",
        "worked in some epochs",
        "attack always worked",
    ]
    return table(header, body)


def usage_table(usages: list[Usage], samples: int | None, epochs: int | None) -> str:
    body: list[list[str]] = []
    total_cost = 0.0
    total_estimate = 0.0
    for usage in usages:
        cost = usage.cost()
        line = [
            label((usage.model, usage.defended)),
            str(usage.sample_epochs),
            f"{usage.input_tokens:,}",
            f"{usage.cache_write_tokens:,}",
            f"{usage.cache_read_tokens:,}",
            f"{usage.output_tokens:,}",
            "unknown price" if cost is None else f"${cost:.2f}",
        ]
        total_cost += cost or 0.0
        if samples and epochs:
            if cost is None or usage.sample_epochs == 0:
                line.append("unknown")
            else:
                estimate = cost / usage.sample_epochs * samples * epochs
                total_estimate += estimate
                line.append(f"${estimate:.2f}")
        body.append(line)

    header = [
        "run",
        "samples x epochs",
        "input",
        "cache write",
        "cache read",
        "output",
        "cost",
    ]
    text = ""
    if samples and epochs:
        header.append(f"estimate for {samples} samples x {epochs} epochs")
        text = f"\n\nEstimated total for the full runs: ${total_estimate:.2f}"
    return (
        table(header, body) + f"\n\nTotal cost of these runs: ${total_cost:.2f}" + text
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_dir", help="directory of Inspect logs")
    parser.add_argument("--estimate-samples", type=int, help="samples in the full run")
    parser.add_argument("--estimate-epochs", type=int, help="epochs in the full run")
    args = parser.parse_args()

    logs = [read_eval_log(info) for info in list_eval_logs(args.log_dir)]
    if not logs:
        raise SystemExit(f"No logs found in {args.log_dir}")
    logs.sort(key=condition_of)  # by model name, baseline before defended
    check_comparable(logs)

    rows: list[Row] = []
    errors: dict[Condition, int] = {}
    for log in logs:
        log_rows, errors[condition_of(log)] = read_rows(log)
        rows += log_rows
    conditions = [condition_of(log) for log in logs]

    settings = dataset_settings(logs[0])
    seed, prs_per_cell = int(str(settings["seed"])), int(str(settings["prs_per_cell"]))
    fingerprint = dataset_hash(build_samples(seed=seed, prs_per_cell=prs_per_cell))

    print("### Runs\n")
    print(run_table(logs))
    print(
        f"\nDataset: seed {seed}, prs_per_cell {prs_per_cell}, demo slice: {settings['demo']}."
    )
    print(f"Hash of the full dataset as generated by this checkout: `{fingerprint}`")
    print("\n### Attack success rate by technique (lower is better)\n")
    print(technique_table(rows, conditions))
    print("\n### Attack success rate by attacker goal (lower is better)\n")
    print(goal_table(rows, conditions))
    print("\n### Usefulness on all samples (higher is better)\n")
    print(usefulness_table(rows, conditions, errors))
    print("\n### Variation across repeated runs (injected samples)\n")
    print(variation_table(rows, conditions))
    print("\n### Token usage and cost\n")
    print(
        usage_table(
            list(map(read_usage, logs)), args.estimate_samples, args.estimate_epochs
        )
    )


if __name__ == "__main__":
    main()
