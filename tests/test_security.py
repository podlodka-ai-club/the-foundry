from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from foundry import security
from foundry.shell import Result


def test_scrubbed_agent_env_keeps_backend_secret_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/bin")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-secret")

    env = security.scrubbed_agent_env("codex_cli")

    assert env["PATH"] == "/bin"
    assert env["OPENAI_API_KEY"] == "sk-openai"
    assert "AWS_SECRET_ACCESS_KEY" not in env


def test_shell_guard_denies_rm_rf() -> None:
    with pytest.raises(RuntimeError, match="rm -rf"):
        security.assert_command_allowed(["rm", "-rf", "/tmp/x"])


def test_shell_guard_denies_force_push() -> None:
    with pytest.raises(RuntimeError, match="push --force"):
        security.assert_command_allowed(["git", "push", "--force", "origin", "main"])


def test_shell_guard_allows_reset_hard_inside_task_worktree(tmp_path: Path) -> None:
    root = tmp_path / "worktrees"
    task = root / "task-9"
    task.mkdir(parents=True)

    security.assert_command_allowed(
        ["git", "reset", "--hard", "HEAD"],
        cwd=task,
        worktree_root=root,
    )


def test_shell_guard_denies_reset_hard_outside_task_worktree(tmp_path: Path) -> None:
    root = tmp_path / "worktrees"
    base = root / "_base"
    base.mkdir(parents=True)

    with pytest.raises(RuntimeError, match="outside task worktree"):
        security.assert_command_allowed(
            ["git", "reset", "--hard", "origin/main"],
            cwd=base,
            worktree_root=root,
        )


def test_shell_guard_denies_checkout_main_in_task_worktree(tmp_path: Path) -> None:
    task = tmp_path / "task-3"
    task.mkdir()

    with pytest.raises(RuntimeError, match="checkout main"):
        security.assert_command_allowed(["git", "checkout", "main"], cwd=task)


def test_checkpoint_diff_captures_intent_to_add_before_diff(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs) -> Result:
        calls.append(cmd)
        return Result(returncode=0, stdout="diff", stderr="")

    with patch("foundry.shell.run", side_effect=fake_run):
        snapshot = security.checkpoint_diff(
            worktree_path=tmp_path / "worktree",
            checkpoint_root=tmp_path / "checkpoints",
            task_id=7,
            attempt=2,
        )

    assert calls[:2] == [["git", "add", "-N", "."], ["git", "diff", "--binary", "HEAD"]]
    assert snapshot.read_text(encoding="utf-8") == "diff"
