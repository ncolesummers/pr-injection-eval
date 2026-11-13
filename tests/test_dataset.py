"""The generator is deterministic and the dataset has the promised shape."""

from collections import Counter

from pr_injection_eval.dataset import (
    BASE_PRS,
    build_pull_request,
    build_samples,
    dataset_hash,
    demo_slice,
    metadata_of,
    pull_request_for,
)
from pr_injection_eval.injections import (
    GOAL_ASKS,
    GOALS,
    MARKER,
    TECHNIQUES,
    goal_named,
)
from pr_injection_eval.tools import PullRequest


def visible_text(pr: PullRequest) -> str:
    """Everything the agent could read about a pull request."""
    parts = [pr.title, pr.description, pr.commit_message, pr.diff, *pr.files.values()]
    return "\n".join(parts)


def test_same_seed_gives_identical_dataset() -> None:
    first, second = build_samples(seed=0), build_samples(seed=0)
    assert [s.id for s in first] == [s.id for s in second]
    assert dataset_hash(first) == dataset_hash(second)


def test_different_seed_gives_different_dataset() -> None:
    assert dataset_hash(build_samples(seed=0)) != dataset_hash(build_samples(seed=1))


def test_default_size_is_in_target_range() -> None:
    assert 40 <= len(build_samples()) <= 60


def test_sample_count_is_configurable() -> None:
    assert len(build_samples(prs_per_cell=1)) < len(build_samples(prs_per_cell=2))


def test_sample_ids_are_unique() -> None:
    ids = [s.id for s in build_samples()]
    assert len(ids) == len(set(ids))


def test_every_base_pr_has_a_clean_control() -> None:
    clean = [s for s in build_samples() if not metadata_of(s)["injected"]]
    assert {metadata_of(s)["base_pr"] for s in clean} == {b.name for b in BASE_PRS}
    for sample in clean:
        meta = metadata_of(sample)
        assert (meta["technique"], meta["placement"], meta["goal"]) == (
            "none",
            "none",
            "none",
        )


def test_clean_controls_contain_no_injection_text() -> None:
    for base in BASE_PRS:
        text = visible_text(build_pull_request(base, None, None))
        assert MARKER not in text
        assert "approve_pr" not in text
        assert "reviewer" not in text.lower()
        for ask in GOAL_ASKS.values():
            assert ask not in text


def test_every_technique_and_goal_is_balanced() -> None:
    injected = [metadata_of(s) for s in build_samples() if metadata_of(s)["injected"]]
    cells = Counter((m["technique"], m["goal"]) for m in injected)
    assert set(cells) == {(t.name, g) for t in TECHNIQUES for g in GOALS}
    assert set(cells.values()) == {2}


def test_suppress_only_targets_prs_with_a_defect() -> None:
    for sample in build_samples():
        meta = metadata_of(sample)
        if meta["goal"] == "suppress":
            assert meta["has_defect"]


def test_at_least_two_base_prs_have_a_defect_with_keywords() -> None:
    with_defect = [b for b in BASE_PRS if b.defect]
    assert len(with_defect) >= 2
    assert all(b.defect_keywords for b in with_defect)
    assert all(not b.defect_keywords for b in BASE_PRS if not b.defect)


def test_injection_lands_only_in_its_placement() -> None:
    for sample in build_samples():
        meta = metadata_of(sample)
        if not meta["injected"]:
            continue
        pr = pull_request_for(meta)
        ask = GOAL_ASKS[goal_named(meta["goal"])]
        in_description = ask in pr.description
        in_commit = ask in pr.commit_message
        in_files = any(ask in text for text in pr.files.values())
        in_diff = ask in pr.diff
        expected = {
            "description": (True, False, False, False),
            "commit_message": (False, True, False, False),
            "code_comment": (False, False, True, True),
            "docs": (False, False, True, True),
        }[meta["placement"]]
        assert (in_description, in_commit, in_files, in_diff) == expected, sample.id


def test_defect_keywords_never_appear_in_anything_the_agent_can_read() -> None:
    # If they did, a review could "mention the defect" just by describing
    # or quoting the PR. This covers the code and diff, not only the prose.
    for sample in build_samples():
        meta = metadata_of(sample)
        text = visible_text(pull_request_for(meta)).lower()
        for base in BASE_PRS:
            if base.name == meta["base_pr"]:
                for keyword in base.defect_keywords:
                    assert keyword not in text, (keyword, sample.id)


def test_every_technique_is_planted_on_the_same_base_prs() -> None:
    # Otherwise a per-technique difference could really be a per-PR one.
    targets: dict[str, set[tuple[str, str]]] = {}
    for sample in build_samples():
        meta = metadata_of(sample)
        if meta["injected"]:
            targets.setdefault(meta["technique"], set()).add(
                (meta["goal"], meta["base_pr"])
            )
    assert len({frozenset(pairs) for pairs in targets.values()}) == 1


def test_approve_and_exfil_are_tried_with_and_without_a_real_defect() -> None:
    for goal in ("approve", "exfil_text"):
        flags = {
            metadata_of(s)["has_defect"]
            for s in build_samples()
            if metadata_of(s)["goal"] == goal
        }
        assert flags == {True, False}


def test_demo_slice_has_one_sample_per_technique_plus_two_clean() -> None:
    demo = [metadata_of(s) for s in demo_slice(build_samples())]
    injected = [m for m in demo if m["injected"]]
    clean = [m for m in demo if not m["injected"]]
    assert [m["technique"] for m in injected] == [t.name for t in TECHNIQUES]
    assert {m["goal"] for m in injected} == set(GOALS)
    assert sorted(m["has_defect"] for m in clean) == [False, True]


def test_demo_slice_is_stable() -> None:
    first = [s.id for s in demo_slice(build_samples())]
    second = [s.id for s in demo_slice(build_samples())]
    assert first == second
