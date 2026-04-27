from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from foundry.coding_agent.providers import DeepSeekProvider
from foundry.coding_agent.runner import AiderResult, run_aider


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    mock = MagicMock()
    mock.returncode = returncode
    mock.stdout = stdout
    mock.stderr = stderr
    return mock


def test_run_aider_builds_command_correctly(tmp_path: Path) -> None:
    provider = DeepSeekProvider(api_key="sk-test", model_name="deepseek/test")

    with patch(
        "foundry.coding_agent.runner.subprocess.run",
        return_value=_completed(0, "ok"),
    ) as mock_run:
        result = run_aider(
            worktree_path=tmp_path,
            task_text="do x",
            files=["a.py", "b.py"],
            provider=provider,
            timeout_seconds=120,
        )

    args, kwargs = mock_run.call_args
    cmd = args[0]
    assert cmd[:3] == ["aider", "--yes-always", "--no-git"]
    assert "--model" in cmd and "deepseek/test" in cmd
    # --file для каждого файла
    assert cmd.count("--file") == 2
    assert "a.py" in cmd and "b.py" in cmd
    # сообщение в конце
    assert cmd[-2] == "--message" and cmd[-1] == "do x"
    assert kwargs["cwd"] == tmp_path
    assert kwargs["timeout"] == 120
    assert result.ok is True


def test_run_aider_returns_failure_on_nonzero_returncode(tmp_path: Path) -> None:
    provider = DeepSeekProvider(api_key="sk-test")

    with patch(
        "foundry.coding_agent.runner.subprocess.run",
        return_value=_completed(2, "", "error msg"),
    ):
        result = run_aider(
            worktree_path=tmp_path,
            task_text="x",
            files=[],
            provider=provider,
        )

    assert result.ok is False
    assert result.returncode == 2
    assert result.stderr == "error msg"


def test_run_aider_handles_timeout(tmp_path: Path) -> None:
    provider = DeepSeekProvider(api_key="sk-test")

    with patch(
        "foundry.coding_agent.runner.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="aider", timeout=5),
    ):
        result = run_aider(
            worktree_path=tmp_path,
            task_text="x",
            files=[],
            provider=provider,
            timeout_seconds=5,
        )

    assert result.ok is False
    assert result.returncode == -1
    assert "timed out" in result.stderr


def test_run_aider_passes_provider_env_to_subprocess(tmp_path: Path) -> None:
    provider = DeepSeekProvider(api_key="sk-secret")

    with patch(
        "foundry.coding_agent.runner.subprocess.run",
        return_value=_completed(0),
    ) as mock_run:
        run_aider(worktree_path=tmp_path, task_text="x", files=[], provider=provider)

    env = mock_run.call_args.kwargs["env"]
    assert env["DEEPSEEK_API_KEY"] == "sk-secret"


def test_run_aider_raises_when_worktree_missing(tmp_path: Path) -> None:
    provider = DeepSeekProvider(api_key="sk-test")
    missing = tmp_path / "nope"
    try:
        run_aider(worktree_path=missing, task_text="x", files=[], provider=provider)
    except FileNotFoundError as exc:
        assert "worktree not found" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_aider_result_dataclass_is_immutable() -> None:
    result = AiderResult(ok=True, returncode=0, stdout="", stderr="", duration_seconds=0.0)
    try:
        result.ok = False  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("AiderResult should be frozen")
