from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from foundry.shell import Result
from foundry.skills.pr import commit_and_push_pr_impl


@pytest.fixture
def pr_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    wt = tmp_path / "task-1"
    wt.mkdir()
    monkeypatch.setenv("FOUNDRY_WORKTREE", str(wt))
    monkeypatch.setenv("FOUNDRY_BRANCH", "foundry/run-1")
    monkeypatch.setenv("FOUNDRY_TARGET_REPO", "owner/target")
    monkeypatch.setenv("FOUNDRY_SOURCE_REPO", "owner/source")
    monkeypatch.setenv("FOUNDRY_ISSUE_NUMBER", "7")
    return wt


def _ok(stdout: str = "") -> Result:
    return Result(returncode=0, stdout=stdout, stderr="")


def test_commit_and_push_pr_happy_path(pr_env: Path) -> None:
    side_effects = [
        _ok(),                                 # git add -A
        _ok(" M README.md\n"),                 # git status --porcelain
        _ok(),                                 # git commit
        _ok(),                                 # git push
        _ok("https://github.com/owner/target/pull/42\n"),  # gh pr create
        _ok(),                                 # gh issue close
    ]

    with patch("foundry.skills.pr.shell.run", side_effect=side_effects) as run_mock:
        out = commit_and_push_pr_impl(title="my pr", body="desc")

    assert out == {"ok": True, "pr_url": "https://github.com/owner/target/pull/42"}
    # Confirm gh pr create was called with our title/body.
    pr_create_call = run_mock.call_args_list[4]
    cmd = pr_create_call.args[0]
    assert "pr" in cmd and "create" in cmd
    assert cmd[cmd.index("--title") + 1] == "my pr"
    assert cmd[cmd.index("--body") + 1] == "desc"


def test_commit_and_push_pr_no_changes(pr_env: Path) -> None:
    side_effects = [_ok(), _ok("")]

    with patch("foundry.skills.pr.shell.run", side_effect=side_effects):
        out = commit_and_push_pr_impl(title="x", body="")

    assert out == {"ok": False, "reason": "no_changes"}


def test_commit_and_push_pr_sanity_failed(pr_env: Path) -> None:
    side_effects = [
        _ok(),
        _ok(" M src/foundry/__pycache__/x.pyc\n"),  # forbidden path
    ]

    with patch("foundry.skills.pr.shell.run", side_effect=side_effects):
        out = commit_and_push_pr_impl(title="x", body="")

    assert out["ok"] is False
    assert out["reason"] == "sanity_failed"


def test_commit_and_push_pr_missing_env_returns_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FOUNDRY_WORKTREE", raising=False)

    out = commit_and_push_pr_impl(title="x", body="")

    assert out["ok"] is False
    assert "missing" in out["error"]
