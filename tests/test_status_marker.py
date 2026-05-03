from __future__ import annotations

import pytest

from foundry.models import FailureKind, RunStatus
from foundry.status_marker import parse_status_marker


def test_done_marker_at_end() -> None:
    text = "Some review text\n\nSTATUS: done"

    assert parse_status_marker(text) == (RunStatus.DONE, None, None)


def test_done_marker_inline() -> None:
    text = "STATUS: done\n\n... and the rest of the report"

    assert parse_status_marker(text) == (RunStatus.DONE, None, None)


def test_failed_without_kind_defaults_to_unclear() -> None:
    assert parse_status_marker("STATUS: failed") == (
        RunStatus.FAILED,
        FailureKind.UNCLEAR,
        None,
    )


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("deterministic", FailureKind.DETERMINISTIC),
        ("acceptance", FailureKind.ACCEPTANCE),
        ("infra", FailureKind.INFRA),
        ("dangerous", FailureKind.DANGEROUS),
        ("unclear", FailureKind.UNCLEAR),
    ],
)
def test_failed_with_kind(kind: str, expected: FailureKind) -> None:
    assert parse_status_marker(f"STATUS: failed:{kind}") == (
        RunStatus.FAILED,
        expected,
        None,
    )


def test_unknown_failure_kind_falls_back_to_unclear() -> None:
    """Defensive: a typoed kind should not crash the orchestrator."""
    assert parse_status_marker("STATUS: failed:nonsense") == (
        RunStatus.FAILED,
        FailureKind.UNCLEAR,
        None,
    )


def test_case_insensitive() -> None:
    assert parse_status_marker("Status: Done") == (RunStatus.DONE, None, None)
    assert parse_status_marker("STATUS: FAILED:ACCEPTANCE") == (
        RunStatus.FAILED,
        FailureKind.ACCEPTANCE,
        None,
    )


def test_last_marker_wins() -> None:
    """Agents sometimes draft a status mid-thought and then revise — the last
    line is the one that counts."""
    text = "STATUS: failed:infra\n... actually no, let me retry ...\nSTATUS: done"

    assert parse_status_marker(text) == (RunStatus.DONE, None, None)


def test_no_marker_returns_none() -> None:
    assert parse_status_marker("just some text without a marker") is None
    assert parse_status_marker("") is None


def test_marker_must_be_on_its_own_line() -> None:
    """A STATUS: substring inside a sentence should NOT match."""
    text = "We tracked the STATUS: done badge in the UI"

    assert parse_status_marker(text) is None


def test_marker_with_trailing_whitespace() -> None:
    assert parse_status_marker("STATUS: done   \n") == (RunStatus.DONE, None, None)


def test_failed_kind_with_spaces_around_colon() -> None:
    assert parse_status_marker("STATUS: failed : acceptance") == (
        RunStatus.FAILED,
        FailureKind.ACCEPTANCE,
        None,
    )


# --- Semantic outcomes (DONE lifecycle + verdict) -------------------------


@pytest.mark.parametrize(
    "outcome",
    ["approved", "change_requested", "rejected"],
)
def test_semantic_outcome_maps_to_done_with_outcome(outcome: str) -> None:
    text = f"## Summary\nReview text.\n\nSTATUS: {outcome}"

    assert parse_status_marker(text) == (RunStatus.DONE, None, outcome)


def test_outcome_is_case_insensitive() -> None:
    assert parse_status_marker("STATUS: APPROVED") == (
        RunStatus.DONE,
        None,
        "approved",
    )


def test_unknown_state_word_returns_none() -> None:
    """Unknown state (e.g. typo) → None so caller treats run as UNCLEAR."""
    assert parse_status_marker("STATUS: maybe_ok") is None


def test_last_outcome_wins_over_done() -> None:
    text = "STATUS: done\nactually let me revise:\nSTATUS: change_requested"

    assert parse_status_marker(text) == (RunStatus.DONE, None, "change_requested")
