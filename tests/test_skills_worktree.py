from __future__ import annotations

from pathlib import Path

import pytest

from foundry.skills.worktree import open_worktree_impl


def test_open_worktree_returns_path_when_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wt = tmp_path / "task-1"
    wt.mkdir()
    monkeypatch.setenv("FOUNDRY_WORKTREE", str(wt))
    monkeypatch.setenv("FOUNDRY_BRANCH", "foundry/run-1")

    out = open_worktree_impl()

    assert out["ok"] is True
    assert out["worktree"] == str(wt)
    assert out["branch"] == "foundry/run-1"


def test_open_worktree_errors_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FOUNDRY_WORKTREE", raising=False)

    out = open_worktree_impl()

    assert out["ok"] is False
    assert "not initialized" in out["error"]
