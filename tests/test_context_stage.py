from __future__ import annotations

from pathlib import Path

from foundry import state
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


def _task() -> Task:
    return Task(
        repo="owner/sandbox",
        issue_number=7,
        issue_title="Make context stage real",
        issue_body="Collect planner context and relevant files for issue keywords.",
    )


def test_context_stage_builds_repo_map_and_relevant_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "context.py").write_text(
        "def collect_context():\n    return 'planner context'\n",
        encoding="utf-8",
    )
    (repo / "tests").mkdir()
    (repo / "tests" / "test_context.py").write_text(
        "def test_context_stage():\n    assert True\n",
        encoding="utf-8",
    )
    settings = _settings(tmp_path)
    state.init_db(settings.db_path)
    state.save_repo_memory(
        settings.db_path, "owner/sandbox", "touched_files", ["src/app.py"]
    )

    out = context.run(_task(), settings, repo_path=repo)

    assert {"language": "Python", "files": 2} in out["languages"]
    assert out["manifest_files"] == ["pyproject.toml"]
    assert out["test_commands"] == ["ruff check .", "pytest -x --no-header -q"]
    assert "context" in out["keywords"]
    assert out["relevant_files"][0]["path"] == "src/context.py"
    assert out["repo_memory"][0]["key"] == "touched_files"
    assert out["files"][0] == "src/context.py"


def test_format_for_prompt_includes_context_sections() -> None:
    prompt = context.format_for_prompt(
        {
            "languages": [{"language": "Python", "files": 3}],
            "manifest_files": ["pyproject.toml"],
            "test_commands": ["pytest -q"],
            "keywords": ["context"],
            "relevant_files": [
                {"path": "src/foundry/stages/context.py", "matched_keywords": ["context"]}
            ],
            "repo_memory": [
                {"repo": "owner/repo", "key": "verify_commands", "value": ["pytest -q"]}
            ],
        }
    )

    assert "## Repository context" in prompt
    assert "`pyproject.toml`" in prompt
    assert "`pytest -q`" in prompt
    assert "`src/foundry/stages/context.py`" in prompt
    assert "### Repo memory" in prompt
    assert "`verify_commands`" in prompt
