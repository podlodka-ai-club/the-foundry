from __future__ import annotations

from pathlib import Path

from foundry.config import Settings
from foundry.models import Task
from foundry.stages import implement


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        source_repo="owner/sandbox",
        target_repo="owner/sandbox",
        issue_label="agent-task",
        worktree_root=tmp_path / "worktrees",
        db_path=tmp_path / "foundry.sqlite",
        poll_interval_seconds=30,
    )


def _task() -> Task:
    return Task(repo="owner/sandbox", issue_number=1, issue_title="t", issue_body="")


def _plan(line: str = "marker") -> dict:
    return {"steps": [{"file": "README.md", "action": "append_line", "line": line}]}


def test_append_line_adds_newline_when_file_has_no_trailing_newline(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_bytes(b"existing content without newline")

    implement.run(_task(), _plan("new line"), tmp_path, _settings(tmp_path))

    assert readme.read_text() == "existing content without newline\nnew line\n"


def test_append_line_no_extra_newline_when_file_ends_with_newline(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("existing\n")

    implement.run(_task(), _plan("new line"), tmp_path, _settings(tmp_path))

    assert readme.read_text() == "existing\nnew line\n"


def test_append_line_on_missing_file_creates_it(tmp_path: Path) -> None:
    implement.run(_task(), _plan("first line"), tmp_path, _settings(tmp_path))

    assert (tmp_path / "README.md").read_text() == "first line\n"


def test_append_line_on_empty_file(tmp_path: Path) -> None:
    (tmp_path / "README.md").touch()

    implement.run(_task(), _plan("only line"), tmp_path, _settings(tmp_path))

    assert (tmp_path / "README.md").read_text() == "only line\n"
