from __future__ import annotations

from foundry.subagents import SUBAGENTS, get_subagent


def test_get_subagent_echo() -> None:
    sub = get_subagent("echo")

    assert sub is not None
    assert sub.name == "echo"
    assert sub.backend == "stub"


def test_get_subagent_missing() -> None:
    assert get_subagent("does-not-exist") is None


def test_subagents_not_empty() -> None:
    assert len(SUBAGENTS) >= 1
    names = {s.name for s in SUBAGENTS}
    assert "echo" in names
