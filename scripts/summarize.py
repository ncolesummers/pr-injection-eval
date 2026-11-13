"""Read Inspect logs and print the results tables as markdown.

Usage:
    uv run python scripts/summarize.py logs/2026-11-13
    uv run python scripts/summarize.py logs/pilot-... --estimate-samples 47 --estimate-epochs 5

It reads every sample of every epoch, not the averaged metrics, so it can
also show how often the same sample came out differently across epochs.
"""

import argparse
from collections import defaultdict
from dataclasses import dataclass

from inspect_ai.log import EvalLog, list_eval_logs, read_eval_log

from pr_injection_eval.injections import TECHNIQUES

# US dollars per million tokens: (input, output). Checked 2026-11-13.
# Cache writes cost 1.25x input and cache reads 0.1x input.
PRICES: dict[str, tuple[float, float]] = {
    "anthropic/claude-haiku-5-5": (0.10, 0.50),
    "anthropic/claude-sonnet-5-5": (2.00, 10.00),
}


@dataclass(frozen=True)
class Row:
    """One sample in one epoch of one run."""

    model: str
    defended: bool
    sample_id: str
    technique: str
    injected: bool
    attack_succeeded: bool | None
    honeypot_called: bool
    review_posted: bool
    defect_caught: bool | None
    useful: bool
    flagged_injection: bool


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
        if self.model not in PRICES:
            return None
        price_in, price_out = PRICES[self.model]
        dollars = (
            self.input_tokens * price_in
            + self.cache_write_tokens * price_in * 1.25
            + self.cache_read_tokens * price_in * 0.1
            + self.output_tokens * price_out
        )
        return dollars / 1_000_000


Condition = tuple[str, bool]  # (model, defended)


def optional_bool(value: object) -> bool | None:
    return None if value is None else bool(value)


def read_rows(log: EvalLog) -> tuple[list[Row], int]:
    """Rows for every scored sample, plus a count of samples that errored."""
    defended = bool(log.eval.task_args.get("defended", False))
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
                model=log.eval.model,
                defended=defended,
                sample_id=str(sample.id),
                technique=str(sample.metadata["technique"]),
                injected=bool(sample.metadata["injected"]),
                attack_succeeded=optional_bool(components["attack_succeeded"]),
                honeypot_called=bool(components["honeypot_called"]),
                review_posted=bool(components["review_posted"]),
                defect_caught=optional_bool(components["defect_caught"]),
                useful=bool(components["useful"]),
                flagged_injection=bool(components["flagged_injection"]),
            )
        )
    return rows, errors


def read_usage(log: EvalLog) -> Usage:
    usage = log.stats.model_usage.get(log.eval.model)
    return Usage(
        model=log.eval.model,
        defended=bool(log.eval.task_args.get("defended", False)),
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


def attack_table(rows: list[Row], conditions: list[Condition]) -> str:
    def cell(condition: Condition, technique: str | None) -> str:
        matching = [
            row
            for row in rows
            if (row.model, row.defended) == condition
            and row.injected
            and technique in (None, row.technique)
        ]
        return rate(
            sum(row.attack_succeeded is True for row in matching), len(matching)
        )

    names: list[str | None] = [technique.name for technique in TECHNIQUES]
    body = [
        [
            name or "**all injected**",
            *(cell(condition, name) for condition in conditions),
        ]
        for name in [*names, None]
    ]
    return table(["technique", *map(label, conditions)], body)


def usefulness_table(rows: list[Row], conditions: list[Condition]) -> str:
    body: list[list[str]] = []
    for condition in conditions:
        mine = [row for row in rows if (row.model, row.defended) == condition]
        with_defect = [row for row in mine if row.defect_caught is not None]
        clean_defect = [row for row in with_defect if not row.injected]
        clean = [row for row in mine if not row.injected]
        injected = [row for row in mine if row.injected]
        body.append(
            [
                label(condition),
                rate(sum(row.useful for row in mine), len(mine)),
                rate(sum(row.review_posted for row in mine), len(mine)),
                rate(
                    sum(row.defect_caught is True for row in with_defect),
                    len(with_defect),
                ),
                rate(
                    sum(row.defect_caught is True for row in clean_defect),
                    len(clean_defect),
                ),
                rate(sum(row.honeypot_called for row in clean), len(clean)),
                rate(sum(row.flagged_injection for row in injected), len(injected)),
            ]
        )
    header = [
        "run",
        "useful",
        "review posted",
        "defect caught (all)",
        "defect caught (clean only)",
        "honeypot called on clean",
        "flagged injection",
    ]
    return table(header, body)


def variation_table(rows: list[Row], conditions: list[Condition]) -> str:
    """How many injected samples gave different outcomes in different epochs."""
    body: list[list[str]] = []
    for condition in conditions:
        outcomes: dict[str, list[bool]] = defaultdict(list)
        for row in rows:
            if (row.model, row.defended) == condition and row.injected:
                outcomes[row.sample_id].append(row.attack_succeeded is True)
        always = sum(all(results) for results in outcomes.values())
        never = sum(not any(results) for results in outcomes.values())
        mixed = len(outcomes) - always - never
        epochs = max((len(results) for results in outcomes.values()), default=0)
        body.append(
            [label(condition), str(epochs), str(never), str(mixed), str(always)]
        )
    header = [
        "run",
        "epochs",
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

    rows: list[Row] = []
    usages: list[Usage] = []
    errors = 0
    for info in list_eval_logs(args.log_dir, descending=False):
        log = read_eval_log(info)
        log_rows, log_errors = read_rows(log)
        rows += log_rows
        errors += log_errors
        usages.append(read_usage(log))

    if not rows:
        raise SystemExit(f"No scored samples found in {args.log_dir}")

    # Small model first, baseline before defended.
    conditions = sorted({(row.model, row.defended) for row in rows})
    usages.sort(key=lambda usage: (usage.model, usage.defended))

    print("### Attack success rate on injected samples (lower is better)\n")
    print(attack_table(rows, conditions))
    print("\n### Usefulness on all samples (higher is better)\n")
    print(usefulness_table(rows, conditions))
    print("\n### Variation across repeated runs (injected samples)\n")
    print(variation_table(rows, conditions))
    print("\n### Token usage and cost\n")
    print(usage_table(usages, args.estimate_samples, args.estimate_epochs))
    if errors:
        print(f"\nSamples skipped because they errored: {errors}")


if __name__ == "__main__":
    main()
