from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Literal

import structlog
from langfuse import observe

from .. import shell
from ..agents import AgentSettings, AgentStage, first_line
from ..config import Settings
from ..models import Task
from . import agent_verify as agent_verify_stage

log = structlog.get_logger()

Verdict = Literal["PASS", "FAIL", "UNCLEAR"]


@observe(name="stage.verify")
def run(
    task: Task,
    worktree_path: Path,
    settings: Settings,
    impl_result: dict | None = None,
) -> dict:
    """Two-tier verification: deterministic gates → agent reviewer.

    Returns a dict consumed by `workflows.normalize_verification`. Keys:
    `passed` (bool, required), `report` (str, human-readable), `stdout` (str,
    deterministic-summary). On failure also: `retryable`, `requires_human`,
    `failure_kind` ∈ {deterministic, acceptance, infra, unclear}.

    Order:
      1. Run each command from `settings.verify_commands` (or auto-detected).
      2. Any non-zero exit → short-circuit with `failure_kind="deterministic"`;
         the agent reviewer is NOT invoked (saves cost, and code that won't
         compile shouldn't get LLM review).
      3. All commands ok → capture diff and call the verify agent.
      4. Parse first line of the agent response: `PASS` / `FAIL: ...` /
         anything else → `unclear` (requires human).
    """
    cmds: list[tuple[str, ...]] = (
        list(settings.verify_commands)
        if settings.verify_commands is not None
        else [tuple(c) for c in _detect_verify_commands(worktree_path)]
    )

    det_outputs: list[dict] = []
    for cmd in cmds:
        try:
            res = shell.run(
                list(cmd),
                cwd=worktree_path,
                check=False,
                timeout=settings.verify_command_timeout_sec,
            )
        except FileNotFoundError:
            return _infra_result(
                " ".join(cmd),
                "executable not found",
                retryable=False,
                requires_human=True,
            )
        except subprocess.TimeoutExpired:
            return _infra_result(
                " ".join(cmd),
                f"timeout after {settings.verify_command_timeout_sec}s",
                retryable=True,
                requires_human=False,
            )
        det_outputs.append(
            {
                "cmd": " ".join(cmd),
                "rc": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
            }
        )
        if not res.ok:
            return _deterministic_failure(det_outputs)

    det_summary = _format_summary(det_outputs)

    if not cmds and _agent_backend_is_stub(settings):
        log.warning("verify.no_checks_configured", task_id=task.id)
        return {
            "passed": True,
            "report": "no checks configured",
            "stdout": det_summary,
        }

    diff_text = _capture_diff(worktree_path, settings.verify_diff_max_bytes)
    try:
        agent_res = agent_verify_stage.run(task, worktree_path, diff_text, settings)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, RuntimeError) as e:
        return _infra_result(
            "agent_verify", str(e), retryable=True, requires_human=False
        )

    response = agent_res.get("response", "")
    verdict = _parse_verdict(response)
    if verdict == "PASS":
        return {
            "passed": True,
            "report": response,
            "stdout": det_summary,
            "cost_usd": agent_res.get("cost_usd"),
            "tokens_in": agent_res.get("tokens_in"),
            "tokens_out": agent_res.get("tokens_out"),
        }
    if verdict == "FAIL":
        return {
            "passed": False,
            "retryable": True,
            "requires_human": False,
            "failure_kind": "acceptance",
            "report": response,
            "stdout": det_summary,
            "cost_usd": agent_res.get("cost_usd"),
            "tokens_in": agent_res.get("tokens_in"),
            "tokens_out": agent_res.get("tokens_out"),
        }
    return {
        "passed": False,
        "retryable": False,
        "requires_human": True,
        "failure_kind": "unclear",
        "report": "agent verdict unparseable: " + first_line(response),
        "stdout": det_summary,
    }


def _detect_verify_commands(worktree_path: Path) -> list[list[str]]:
    """Pick reasonable default check commands by sniffing project markers.

    Empty list when no marker matches — the caller decides whether to fail
    open or to require an explicit `VERIFY_COMMANDS` override.
    """
    cmds: list[list[str]] = []
    if (worktree_path / "pyproject.toml").exists():
        cmds.append(["uv", "run", "ruff", "check", "."])
        if (worktree_path / "tests").is_dir():
            cmds.append(["uv", "run", "pytest", "-x", "--no-header", "-q"])
    if (worktree_path / "package.json").exists():
        cmds.extend(_npm_commands(worktree_path, Path(".")))
    for package_json in sorted(worktree_path.glob("*/package.json")):
        package_dir = package_json.parent.relative_to(worktree_path)
        cmds.extend(_npm_commands(worktree_path, package_dir))
    if (worktree_path / "Cargo.toml").exists():
        cmds.append(["cargo", "test"])
    return _dedupe_commands(cmds)


def _npm_commands(root: Path, package_dir: Path) -> list[list[str]]:
    package_root = root / package_dir
    package_json = _read_package_json(package_root / "package.json")
    scripts = package_json.get("scripts", {})
    if not isinstance(scripts, dict):
        scripts = {}

    prefix = [] if package_dir.as_posix() == "." else ["--prefix", package_dir.as_posix()]
    cmds: list[list[str]] = []
    if (package_root / "package-lock.json").exists():
        cmds.append(["npm", *prefix, "ci"])
    for script in ("build", "lint", "test"):
        if script in scripts:
            suffix = ["--silent"] if script == "test" else []
            cmds.append(["npm", *prefix, "run", script, *suffix])
    return cmds


def _read_package_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _dedupe_commands(cmds: list[list[str]]) -> list[list[str]]:
    out: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for cmd in cmds:
        key = tuple(cmd)
        if key in seen:
            continue
        seen.add(key)
        out.append(cmd)
    return out


def _capture_diff(worktree_path: Path, max_bytes: int) -> str:
    """Snapshot all working-tree changes (including untracked) as unified diff.

    `git add -N .` registers untracked files as intent-to-add so they appear
    in `git diff` without being staged — the subsequent `pr.py` `git add -A`
    is unaffected. Truncates to `--stat` summary if the raw diff exceeds the
    byte cap; partial diffs are misleading to the reviewer.
    """
    shell.run(["git", "add", "-N", "."], cwd=worktree_path, check=False, timeout=30)
    res = shell.run(
        ["git", "diff", "--no-color"],
        cwd=worktree_path,
        check=False,
        timeout=30,
    )
    diff = res.stdout
    if len(diff.encode("utf-8")) > max_bytes:
        stat = shell.run(
            ["git", "diff", "--stat"],
            cwd=worktree_path,
            check=False,
            timeout=30,
        )
        diff = (
            stat.stdout
            + f"\n--- diff truncated, full body exceeded {max_bytes} bytes ---\n"
        )
    return diff


def _parse_verdict(response: str) -> Verdict:
    line = first_line(response).strip()
    if line == "PASS":
        return "PASS"
    if line.startswith("FAIL"):
        return "FAIL"
    return "UNCLEAR"


def _agent_backend_is_stub(settings: Settings) -> bool:
    return AgentSettings.from_env(AgentStage.VERIFY, db_path=settings.db_path).backend == "stub"


def _format_summary(outputs: list[dict]) -> str:
    if not outputs:
        return ""
    lines = []
    for o in outputs:
        status = "ok" if o["rc"] == 0 else f"rc={o['rc']}"
        lines.append(f"{o['cmd']} → {status}")
    return "\n".join(lines)


def _deterministic_failure(outputs: list[dict]) -> dict:
    last = outputs[-1]
    tail = (last["stderr"] or last["stdout"] or "").strip()
    report_lines = [f"`{last['cmd']}` failed (rc={last['rc']})"]
    if tail:
        report_lines.append("")
        report_lines.append(tail[-2000:])
    return {
        "passed": False,
        "retryable": True,
        "requires_human": False,
        "failure_kind": "deterministic",
        "report": "\n".join(report_lines),
        "stdout": _format_summary(outputs),
    }


def _infra_result(
    cmd: str, msg: str, *, retryable: bool, requires_human: bool
) -> dict:
    return {
        "passed": False,
        "retryable": retryable,
        "requires_human": requires_human,
        "failure_kind": "infra",
        "report": f"infra failure in `{cmd}`: {msg}",
        "stdout": "",
    }
