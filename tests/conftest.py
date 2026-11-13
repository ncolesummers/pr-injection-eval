"""Shared test helpers."""

from collections.abc import Iterator

import pytest
from inspect_ai.util import store_as

from pr_injection_eval.tools import PullRequest, ReviewSession

EXAMPLE_PR = PullRequest(
    title="Add greeting",
    description="Adds a greeting helper.",
    commit_message="Add greeting helper",
    diff="+def greet() -> str:\n+    return 'hi'\n",
    files={"src/greet.py": "def greet() -> str:\n    return 'hi'\n", "README.md": "x"},
)


@pytest.fixture
def session() -> Iterator[ReviewSession]:
    """A fresh review session holding EXAMPLE_PR.

    Outside a running eval, Inspect uses one shared store, so each test
    resets it before and after.
    """
    current = store_as(ReviewSession)
    current.pull_request = EXAMPLE_PR
    current.comments = []
    current.approvals = []
    yield current
    current.pull_request = None
    current.comments = []
    current.approvals = []
