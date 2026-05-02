from __future__ import annotations

from unittest.mock import patch

import pytest

from foundry.shell import Result
from foundry.skills.github import react_emoji_impl


def test_react_emoji_known_emoji_invokes_gh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_SOURCE_REPO", "owner/repo")
    monkeypatch.setenv("FOUNDRY_ISSUE_NUMBER", "9")

    with patch(
        "foundry.skills.github.shell.run",
        return_value=Result(returncode=0, stdout="", stderr=""),
    ) as run_mock:
        out = react_emoji_impl(emoji="rocket")

    assert out == {"ok": True}
    cmd = run_mock.call_args.args[0]
    assert cmd[0:2] == ["gh", "api"]
    assert "repos/owner/repo/issues/9/reactions" in cmd
    assert "content=rocket" in cmd


def test_react_emoji_unknown_emoji_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_SOURCE_REPO", "owner/repo")
    monkeypatch.setenv("FOUNDRY_ISSUE_NUMBER", "9")

    with patch("foundry.skills.github.shell.run") as run_mock:
        out = react_emoji_impl(emoji="confetti")

    assert out["ok"] is False
    assert out["error"] == "unknown emoji"
    run_mock.assert_not_called()
