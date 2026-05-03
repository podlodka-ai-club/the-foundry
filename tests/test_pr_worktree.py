from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from foundry import pr_worktree
from foundry.shell import Result


def _make_fake_repo(path: Path, *, with_commit: bool = True) -> None:
    """Init a tiny git repo so discovery's .git check + remote-url work."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=path, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    if with_commit:
        (path / "README.md").write_text("hello\n")
        subprocess.run(["git", "add", "."], cwd=path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)


def _set_origin(path: Path, url: str) -> None:
    subprocess.run(
        ["git", "remote", "add", "origin", url], cwd=path, check=True
    )


# --- _normalize_slug ---


def test_normalize_slug_handles_ssh_form() -> None:
    assert (
        pr_worktree._normalize_slug("git@github.com:owner/name.git") == "owner/name"
    )


def test_normalize_slug_handles_https_form() -> None:
    assert (
        pr_worktree._normalize_slug("https://github.com/owner/name.git")
        == "owner/name"
    )


def test_normalize_slug_strips_dot_git_only_when_present() -> None:
    assert (
        pr_worktree._normalize_slug("https://github.com/owner/name") == "owner/name"
    )


def test_normalize_slug_returns_none_for_garbage() -> None:
    assert pr_worktree._normalize_slug("") is None
    assert pr_worktree._normalize_slug("not-a-url") is None


# --- discover_repos ---


def test_discover_repos_picks_up_direct_subdir(tmp_path: Path) -> None:
    repo = tmp_path / "lium-io"
    _make_fake_repo(repo)
    _set_origin(repo, "git@github.com:Datura-ai/lium-io.git")

    found = pr_worktree.discover_repos(tmp_path)

    assert found == {"Datura-ai/lium-io": repo}


def test_discover_repos_picks_up_one_level_deeper(tmp_path: Path) -> None:
    repo = tmp_path / "chutes" / "chutes-miner"
    _make_fake_repo(repo)
    _set_origin(repo, "https://github.com/chutesai/chutes-miner.git")

    found = pr_worktree.discover_repos(tmp_path)

    assert found == {"chutesai/chutes-miner": repo}


def test_discover_repos_skips_non_git_subdirs(tmp_path: Path) -> None:
    (tmp_path / "not-a-repo").mkdir()
    (tmp_path / "not-a-repo" / "file.txt").write_text("x")
    repo = tmp_path / "lium-io"
    _make_fake_repo(repo)
    _set_origin(repo, "git@github.com:Datura-ai/lium-io.git")

    found = pr_worktree.discover_repos(tmp_path)

    assert found == {"Datura-ai/lium-io": repo}


def test_discover_repos_returns_empty_for_missing_base(tmp_path: Path) -> None:
    found = pr_worktree.discover_repos(tmp_path / "does-not-exist")

    assert found == {}


# --- prepare_pr_worktree ---


def test_prepare_pr_worktree_runs_fetch_worktree_rsync(
    tmp_path: Path,
) -> None:
    """Mocks shell.run to capture the command sequence the helper issues."""
    repo = tmp_path / "lium-io"
    _make_fake_repo(repo)
    _set_origin(repo, "git@github.com:Datura-ai/lium-io.git")

    calls: list[list[str]] = []

    def fake_run(cmd, cwd=None, check=True, timeout=120, env=None):
        calls.append(cmd)
        # Simulate `git remote get-url origin` for discovery.
        if cmd[:3] == ["git", "remote", "get-url"]:
            return Result(returncode=0, stdout="git@github.com:Datura-ai/lium-io.git\n", stderr="")
        return Result(returncode=0, stdout="", stderr="")

    with patch("foundry.pr_worktree.shell.run", side_effect=fake_run):
        wt_path, branch, cleanup = pr_worktree.prepare_pr_worktree(
            base_path=tmp_path,
            repo="Datura-ai/lium-io",
            head_sha="abc1234567890",
            run_id=7,
        )

    assert wt_path == tmp_path / "_foundry-pr-7-lium-io"
    assert branch == "abc123456789"  # 12-char prefix

    cmds = [c for c in calls if c[:1] == ["git"] or c[:1] == ["rsync"]]
    # Expect fetch, worktree add, rsync (in that order).
    fetch = next(c for c in cmds if c[:2] == ["git", "fetch"])
    assert "abc1234567890" in fetch
    worktree_add = next(c for c in cmds if c[:3] == ["git", "worktree", "add"])
    assert "--detach" in worktree_add
    assert str(wt_path) in worktree_add
    assert "abc1234567890" in worktree_add
    rsync = next(c for c in cmds if c[0] == "rsync")
    assert "--include=*.md" in rsync
    assert "--include=.claude/***" in rsync
    assert "--include=.agents/***" in rsync


def test_prepare_pr_worktree_raises_when_repo_unknown(tmp_path: Path) -> None:
    """No matching repo under base → PrWorktreeError."""
    with pytest.raises(pr_worktree.PrWorktreeError) as excinfo:
        pr_worktree.prepare_pr_worktree(
            base_path=tmp_path,
            repo="ghost/repo",
            head_sha="abc",
            run_id=1,
        )

    assert "no local checkout" in str(excinfo.value)


def test_prepare_pr_worktree_cleanup_removes_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "lium-io"
    _make_fake_repo(repo)
    _set_origin(repo, "git@github.com:Datura-ai/lium-io.git")

    cleanup_calls: list[list[str]] = []

    def fake_run(cmd, cwd=None, check=True, timeout=120, env=None):
        if cmd[:3] == ["git", "remote", "get-url"]:
            return Result(returncode=0, stdout="git@github.com:Datura-ai/lium-io.git\n", stderr="")
        if cmd[:3] == ["git", "worktree", "remove"]:
            cleanup_calls.append(cmd)
        return Result(returncode=0, stdout="", stderr="")

    with patch("foundry.pr_worktree.shell.run", side_effect=fake_run):
        _, _, cleanup = pr_worktree.prepare_pr_worktree(
            base_path=tmp_path,
            repo="Datura-ai/lium-io",
            head_sha="deadbeef",
            run_id=3,
        )
        cleanup()

    assert any(c[:3] == ["git", "worktree", "remove"] for c in cleanup_calls)
