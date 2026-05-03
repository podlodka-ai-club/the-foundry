from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from foundry.config import ConfigError, Settings, _parse_verify_commands
from foundry.models import Task
from foundry.shell import Result
from foundry.stages import verify as verify_stage


# ----- fixtures -----------------------------------------------------------


def _settings(tmp_path: Path, **overrides) -> Settings:
    defaults = dict(
        source_repo="owner/sandbox",
        target_repo="owner/sandbox",
        issue_label="agent-task",
        worktree_root=tmp_path / "worktrees",
        db_path=tmp_path / "foundry.sqlite",
        poll_interval_seconds=30,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _task() -> Task:
    return Task(id=1, repo="owner/sandbox", issue_number=42, issue_title="t", issue_body="b")


def _ok(stdout: str = "") -> Result:
    return Result(returncode=0, stdout=stdout, stderr="")


def _fail(returncode: int = 1, stderr: str = "boom") -> Result:
    return Result(returncode=returncode, stdout="", stderr=stderr)


def _shell_router(handlers: dict[tuple[str, ...], Result]):
    """Build a shell.run side_effect that dispatches by command prefix.

    Each key is a tuple of leading argv words to match; the longest match wins.
    Falls back to a successful empty result for unmatched commands so
    incidental git operations in `_capture_diff` don't blow up tests that
    don't care about them.
    """
    def _run(cmd, cwd=None, check=True, timeout=120, env=None):
        for prefix, result in sorted(handlers.items(), key=lambda kv: -len(kv[0])):
            if tuple(cmd[: len(prefix)]) == prefix:
                return result
        return _ok()
    return _run


# ----- _parse_verify_commands ---------------------------------------------


def test_parse_verify_commands_empty_returns_none() -> None:
    assert _parse_verify_commands("") is None
    assert _parse_verify_commands("   ") is None


def test_parse_verify_commands_valid_json() -> None:
    parsed = _parse_verify_commands('[["ruff","check","."],["pytest","-x"]]')
    assert parsed == (("ruff", "check", "."), ("pytest", "-x"))


def test_parse_verify_commands_rejects_invalid_json() -> None:
    with pytest.raises(ConfigError):
        _parse_verify_commands("not json")


def test_parse_verify_commands_rejects_wrong_shape() -> None:
    with pytest.raises(ConfigError):
        _parse_verify_commands('"just a string"')
    with pytest.raises(ConfigError):
        _parse_verify_commands('[["ok"], "not-a-list"]')
    with pytest.raises(ConfigError):
        _parse_verify_commands('[[]]')  # empty argv


# ----- _detect_verify_commands --------------------------------------------


def test_detect_pyproject_with_tests_returns_ruff_and_pytest(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "tests").mkdir()
    cmds = verify_stage._detect_verify_commands(tmp_path)
    assert cmds == [
        ["uv", "run", "ruff", "check", "."],
        ["uv", "run", "pytest", "-x", "--no-header", "-q"],
    ]


def test_detect_pyproject_without_tests_omits_pytest(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    cmds = verify_stage._detect_verify_commands(tmp_path)
    assert cmds == [["uv", "run", "ruff", "check", "."]]


def test_detect_no_markers_returns_empty(tmp_path: Path) -> None:
    assert verify_stage._detect_verify_commands(tmp_path) == []


def test_detect_package_json(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"scripts":{"build":"vite build","lint":"eslint .","test":"vitest"}}'
    )
    (tmp_path / "package-lock.json").write_text("{}")
    assert verify_stage._detect_verify_commands(tmp_path) == [
        ["npm", "ci"],
        ["npm", "run", "build"],
        ["npm", "run", "lint"],
        ["npm", "run", "test", "--silent"],
    ]


def test_detect_nested_package_json_installs_and_runs_scripts(tmp_path: Path) -> None:
    web = tmp_path / "web"
    web.mkdir()
    (web / "package.json").write_text('{"scripts":{"build":"tsc","lint":"eslint ."}}')
    (web / "package-lock.json").write_text("{}")

    assert verify_stage._detect_verify_commands(tmp_path) == [
        ["npm", "--prefix", "web", "ci"],
        ["npm", "--prefix", "web", "run", "build"],
        ["npm", "--prefix", "web", "run", "lint"],
    ]


# ----- _parse_verdict -----------------------------------------------------


def test_parse_verdict_pass() -> None:
    assert verify_stage._parse_verdict("PASS\nall good") == "PASS"


def test_parse_verdict_fail() -> None:
    assert verify_stage._parse_verdict("FAIL: missing test") == "FAIL"
    assert verify_stage._parse_verdict("FAIL\ndetails") == "FAIL"


def test_parse_verdict_unclear() -> None:
    assert verify_stage._parse_verdict("hmm dunno") == "UNCLEAR"
    assert verify_stage._parse_verdict("pass") == "UNCLEAR"  # case-sensitive


# ----- run() — full orchestrator ------------------------------------------


def test_all_deterministic_pass_plus_stub_agent_passes(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    wt.mkdir()
    settings = _settings(tmp_path, verify_commands=(("ruff", "check", "."),))

    with patch.object(verify_stage.shell, "run", side_effect=_shell_router({
        ("ruff",): _ok("ok"),
    })), patch.object(
        verify_stage.agent_verify_stage,
        "run",
        return_value={
            "agent": "stub",
            "stage": "verify",
            "result": "PASS",
            "response": "PASS\nstub always verifies PASS",
            "cost_usd": None,
            "tokens_in": None,
            "tokens_out": None,
        },
    ):
        result = verify_stage.run(_task(), wt, settings)

    assert result["passed"] is True
    assert "PASS" in result["report"]
    assert "ruff check ." in result["stdout"]
    assert "failure_kind" not in result


def test_deterministic_failure_short_circuits_agent(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    wt.mkdir()
    settings = _settings(tmp_path, verify_commands=(("ruff", "check", "."),))

    with patch.object(verify_stage.shell, "run", side_effect=_shell_router({
        ("ruff",): _fail(stderr="E501 line too long"),
    })), patch.object(verify_stage.agent_verify_stage, "run") as agent_mock:
        result = verify_stage.run(_task(), wt, settings)

    assert result["passed"] is False
    assert result["failure_kind"] == "deterministic"
    assert result["retryable"] is True
    assert result["requires_human"] is False
    assert "ruff" in result["report"]
    assert "E501" in result["report"]
    agent_mock.assert_not_called()


def test_agent_fail_returns_acceptance(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    wt.mkdir()
    settings = _settings(tmp_path, verify_commands=(("true",),))

    with patch.object(verify_stage.shell, "run", side_effect=_shell_router({
        ("true",): _ok(),
    })), patch.object(
        verify_stage.agent_verify_stage,
        "run",
        return_value={"response": "FAIL: missing test for new path", "result": "FAIL: ..."},
    ):
        result = verify_stage.run(_task(), wt, settings)

    assert result["passed"] is False
    assert result["failure_kind"] == "acceptance"
    assert result["retryable"] is True
    assert result["requires_human"] is False
    assert "missing test" in result["report"]


def test_agent_unparseable_verdict_requires_human(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    wt.mkdir()
    settings = _settings(tmp_path, verify_commands=())

    # Empty verify_commands tuple → cmds list is empty, but we want to reach
    # the agent path. Use a non-stub-looking backend so the no-checks branch
    # doesn't short-circuit.
    with patch.object(verify_stage.shell, "run", side_effect=_shell_router({})), \
         patch.object(verify_stage, "_agent_backend_is_stub", return_value=False), \
         patch.object(
             verify_stage.agent_verify_stage,
             "run",
             return_value={"response": "hmm dunno", "result": "hmm dunno"},
         ):
        result = verify_stage.run(_task(), wt, settings)

    assert result["passed"] is False
    assert result["failure_kind"] == "unclear"
    assert result["requires_human"] is True
    assert result["retryable"] is False


def test_shell_timeout_is_infra(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    wt.mkdir()
    settings = _settings(tmp_path, verify_commands=(("pytest",),))

    def _run(cmd, **kw):
        if cmd[0] == "pytest":
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=300)
        return _ok()

    with patch.object(verify_stage.shell, "run", side_effect=_run), \
         patch.object(verify_stage.agent_verify_stage, "run") as agent_mock:
        result = verify_stage.run(_task(), wt, settings)

    assert result["passed"] is False
    assert result["failure_kind"] == "infra"
    assert result["retryable"] is True
    assert result["requires_human"] is False
    assert "timeout" in result["report"].lower()
    agent_mock.assert_not_called()


def test_missing_executable_is_infra_non_retryable(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    wt.mkdir()
    settings = _settings(tmp_path, verify_commands=(("nonexistent-binary",),))

    def _run(cmd, **kw):
        if cmd[0] == "nonexistent-binary":
            raise FileNotFoundError(2, "No such file or directory: 'nonexistent-binary'")
        return _ok()

    with patch.object(verify_stage.shell, "run", side_effect=_run), \
         patch.object(verify_stage.agent_verify_stage, "run") as agent_mock:
        result = verify_stage.run(_task(), wt, settings)

    assert result["passed"] is False
    assert result["failure_kind"] == "infra"
    assert result["retryable"] is False
    assert result["requires_human"] is True
    assert "executable not found" in result["report"]
    agent_mock.assert_not_called()


def test_verify_commands_env_replaces_autodetect(tmp_path: Path) -> None:
    """Even with a pyproject.toml present, an explicit verify_commands tuple wins."""
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / "pyproject.toml").write_text("[project]\nname='x'\n")
    (wt / "tests").mkdir()
    settings = _settings(tmp_path, verify_commands=(("true",),))

    seen_cmds: list[list[str]] = []

    def _run(cmd, **kw):
        seen_cmds.append(list(cmd))
        return _ok()

    with patch.object(verify_stage.shell, "run", side_effect=_run), \
         patch.object(
             verify_stage.agent_verify_stage,
             "run",
             return_value={"response": "PASS", "result": "PASS"},
         ):
        verify_stage.run(_task(), wt, settings)

    # Only `true` from override + git plumbing for diff capture; no ruff or pytest.
    det_cmds = [c for c in seen_cmds if c[0] not in ("git",)]
    assert det_cmds == [["true"]]


def test_diff_truncation_replaces_with_stat(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    wt.mkdir()
    settings = _settings(tmp_path, verify_commands=(("true",),), verify_diff_max_bytes=100)

    big_diff = "+" * 5000
    captured: dict = {}

    def _run(cmd, **kw):
        if cmd[0] == "true":
            return _ok()
        if cmd[:2] == ["git", "add"]:
            return _ok()
        if cmd[:3] == ["git", "diff", "--stat"]:
            return _ok(" 1 file changed, 5000 insertions(+)\n")
        if cmd[:2] == ["git", "diff"]:
            return _ok(big_diff)
        return _ok()

    def _agent_run(task, worktree, diff_text, settings):
        captured["diff"] = diff_text
        return {"response": "PASS", "result": "PASS"}

    with patch.object(verify_stage.shell, "run", side_effect=_run), \
         patch.object(verify_stage.agent_verify_stage, "run", side_effect=_agent_run):
        verify_stage.run(_task(), wt, settings)

    assert "5000 insertions" in captured["diff"]
    assert "diff truncated" in captured["diff"]
    assert big_diff not in captured["diff"]


def test_no_checks_configured_passes_with_warning(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    wt.mkdir()
    # No pyproject/package/cargo markers → auto-detect returns empty.
    settings = _settings(tmp_path)

    with patch.object(verify_stage.shell, "run", side_effect=_shell_router({})), \
         patch.object(verify_stage, "_agent_backend_is_stub", return_value=True), \
         patch.object(verify_stage.agent_verify_stage, "run") as agent_mock:
        result = verify_stage.run(_task(), wt, settings)

    assert result["passed"] is True
    assert result["report"] == "no checks configured"
    agent_mock.assert_not_called()
