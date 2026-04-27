from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from foundry.coding_agent.runner import AiderResult
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
        coding_llm="DEEPSEEK",
        deepseek_api_key="sk-test",
    )


def _task() -> Task:
    return Task(repo="owner/sandbox", issue_number=1, issue_title="t", issue_body="")


def _plan(task_text: str = "do x", files: list[str] | None = None) -> dict:
    return {
        "steps": [
            {
                "kind": "aider_run",
                "task_text": task_text,
                "files": files or [],
            }
        ]
    }


def _success_result() -> AiderResult:
    return AiderResult(
        ok=True, returncode=0, stdout="aider stdout", stderr="", duration_seconds=1.5
    )


def test_implement_invokes_aider_with_task_text(tmp_path: Path) -> None:
    fake_provider = MagicMock()
    fake_provider.get_provider_name.return_value = "DeepSeek"
    fake_provider.get_model_name.return_value = "deepseek/deepseek-chat"
    fake_provider.post_process_files.return_value = []

    with patch(
        "foundry.stages.implement.LLMProviderFactory.create_from_settings",
        return_value=fake_provider,
    ), patch(
        "foundry.stages.implement.run_aider", return_value=_success_result()
    ) as mock_run:
        implement.run(
            _task(), _plan("write hello.py", ["a.py"]), tmp_path, _settings(tmp_path)
        )

    kwargs = mock_run.call_args.kwargs
    assert kwargs["worktree_path"] == tmp_path
    assert kwargs["task_text"] == "write hello.py"
    assert kwargs["files"] == ["a.py"]
    assert kwargs["provider"] is fake_provider
    assert kwargs["timeout_seconds"] == 600


def test_implement_returns_structured_result(tmp_path: Path) -> None:
    fake_provider = MagicMock()
    fake_provider.get_provider_name.return_value = "DeepSeek"
    fake_provider.get_model_name.return_value = "deepseek/deepseek-chat"
    fake_provider.post_process_files.return_value = [("bad.py", "good.py")]

    with patch(
        "foundry.stages.implement.LLMProviderFactory.create_from_settings",
        return_value=fake_provider,
    ), patch(
        "foundry.stages.implement.run_aider", return_value=_success_result()
    ):
        result = implement.run(_task(), _plan(), tmp_path, _settings(tmp_path))

    assert result["ok"] is True
    assert result["provider"] == "DeepSeek"
    assert result["model"] == "deepseek/deepseek-chat"
    assert result["returncode"] == 0
    assert result["renamed_files"] == [("bad.py", "good.py")]
    assert "stdout_tail" in result
    assert "duration_seconds" in result


def test_implement_raises_on_aider_failure(tmp_path: Path) -> None:
    fake_provider = MagicMock()
    fake_provider.get_provider_name.return_value = "DeepSeek"
    fake_provider.post_process_files.return_value = []
    failed = AiderResult(
        ok=False, returncode=2, stdout="", stderr="boom", duration_seconds=0.1
    )

    with patch(
        "foundry.stages.implement.LLMProviderFactory.create_from_settings",
        return_value=fake_provider,
    ), patch("foundry.stages.implement.run_aider", return_value=failed):
        with pytest.raises(RuntimeError, match="aider failed"):
            implement.run(_task(), _plan(), tmp_path, _settings(tmp_path))


def test_implement_calls_post_process_files(tmp_path: Path) -> None:
    fake_provider = MagicMock()
    fake_provider.get_provider_name.return_value = "DeepSeek"
    fake_provider.get_model_name.return_value = "deepseek/deepseek-chat"
    fake_provider.post_process_files.return_value = []

    with patch(
        "foundry.stages.implement.LLMProviderFactory.create_from_settings",
        return_value=fake_provider,
    ), patch("foundry.stages.implement.run_aider", return_value=_success_result()):
        implement.run(_task(), _plan(), tmp_path, _settings(tmp_path))

    fake_provider.post_process_files.assert_called_once_with(tmp_path)
