from __future__ import annotations

from pathlib import Path

from foundry.config import Settings
from foundry.models import Task
from foundry.stages import context


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        source_repo="owner/sandbox",
        target_repo="owner/sandbox",
        issue_label="agent-task",
        worktree_root=tmp_path / "worktrees",
        db_path=tmp_path / "foundry.sqlite",
        poll_interval_seconds=30,
    )


def _task(worktree: Path, *, title: str = "Title", body: str = "Body") -> Task:
    return Task(
        repo="owner/sandbox",
        issue_number=42,
        issue_title=title,
        issue_body=body,
        worktree_path=str(worktree),
    )


def test_context_collects_files_in_worktree(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print('hi')")
    (tmp_path / "README.md").write_text("# hi")
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "mod.py").write_text("x = 1")

    ctx = context.run(_task(tmp_path), _settings(tmp_path))

    assert sorted(ctx["files"]) == ["README.md", "main.py", "pkg/mod.py"]
    assert ctx["worktree_path"] == str(tmp_path)


def test_context_excludes_dotgit_and_caches(tmp_path: Path) -> None:
    (tmp_path / "keep.py").write_text("k = 1")
    git = tmp_path / ".git"
    git.mkdir()
    (git / "HEAD").write_text("ref: refs/heads/main")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "x.pyc").write_text("")
    (tmp_path / ".aider.input.history").write_text("")

    ctx = context.run(_task(tmp_path), _settings(tmp_path))

    assert ctx["files"] == ["keep.py"]


def test_context_builds_task_text_from_issue(tmp_path: Path) -> None:
    ctx = context.run(
        _task(tmp_path, title="Add hello", body="Print Hello World"),
        _settings(tmp_path),
    )

    assert ctx["task_text"] == "# Add hello\n\nPrint Hello World"


def test_context_handles_empty_body(tmp_path: Path) -> None:
    ctx = context.run(_task(tmp_path, title="Just a title", body=""), _settings(tmp_path))

    assert ctx["task_text"] == "# Just a title"
