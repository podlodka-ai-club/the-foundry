from __future__ import annotations

import os
from pathlib import Path

TRUTHY = {"1", "true", "yes", "on"}
BASE_ENV_ALLOWLIST = {
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "TERM",
    "LANG",
    "LC_ALL",
    "TMPDIR",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_STATE_HOME",
    "SSH_AUTH_SOCK",
}
BACKEND_SECRET_ALLOWLIST: dict[str, set[str]] = {
    "claude_cli": {"ANTHROPIC_API_KEY"},
    "codex_cli": {"OPENAI_API_KEY"},
    "opencode_cli": {
        "ANTHROPIC_API_KEY",
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
    },
}


def is_safe_agent_mode(raw: str | None = None) -> bool:
    if raw is None:
        raw = os.getenv("SAFE_AGENT_MODE", "true")
    return raw.strip().lower() in TRUTHY


def scrubbed_agent_env(backend: str, extra_allowlist: str | None = None) -> dict[str, str]:
    allowed = set(BASE_ENV_ALLOWLIST)
    allowed |= BACKEND_SECRET_ALLOWLIST.get(backend, set())
    raw_extra = extra_allowlist
    if raw_extra is None:
        raw_extra = os.getenv("AGENT_ENV_ALLOWLIST", "")
    allowed |= {item.strip() for item in raw_extra.split(",") if item.strip()}
    return {key: value for key, value in os.environ.items() if key in allowed}


def assert_command_allowed(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    worktree_root: Path | None = None,
) -> None:
    if not cmd:
        return
    if _is_rm_rf(cmd):
        raise RuntimeError("refusing unsafe shell command: rm -rf is denied")
    if cmd[0] != "git":
        return
    args = cmd[1:]
    if _is_git_force_push(args):
        raise RuntimeError("refusing unsafe shell command: git push --force is denied")
    if _is_git_checkout_main(args) and _is_task_worktree(cwd, worktree_root):
        raise RuntimeError("refusing unsafe shell command: git checkout main in task worktree")
    if _is_git_reset_hard(args) and not _is_task_worktree(cwd, worktree_root):
        raise RuntimeError(
            "refusing unsafe shell command: git reset --hard outside task worktree"
        )


def checkpoint_diff(
    *,
    worktree_path: Path,
    checkpoint_root: Path,
    task_id: int,
    attempt: int,
) -> Path:
    from . import shell

    checkpoint_root.mkdir(parents=True, exist_ok=True)
    snapshot = checkpoint_root / f"task-{task_id}-attempt-{attempt}-pre.diff"
    shell.run(["git", "add", "-N", "."], cwd=worktree_path, check=False)
    diff = shell.run(["git", "diff", "--binary", "HEAD"], cwd=worktree_path)
    snapshot.write_text(diff.stdout, encoding="utf-8")
    return snapshot


def reset_task_worktree(worktree_path: Path, worktree_root: Path) -> None:
    from . import shell

    shell.run(
        ["git", "reset", "--hard", "HEAD"],
        cwd=worktree_path,
        worktree_root=worktree_root,
    )


def _is_rm_rf(cmd: list[str]) -> bool:
    if cmd[0] != "rm":
        return False
    flags = "".join(arg[1:] for arg in cmd[1:] if arg.startswith("-"))
    return "r" in flags and "f" in flags


def _is_git_force_push(args: list[str]) -> bool:
    return bool(args) and args[0] == "push" and any(
        arg == "--force" or arg == "-f" or arg.startswith("--force-with-lease")
        for arg in args[1:]
    )


def _is_git_checkout_main(args: list[str]) -> bool:
    return len(args) >= 2 and args[0] in {"checkout", "switch"} and args[-1] == "main"


def _is_git_reset_hard(args: list[str]) -> bool:
    return len(args) >= 2 and args[0] == "reset" and "--hard" in args[1:]


def _is_task_worktree(cwd: Path | None, worktree_root: Path | None) -> bool:
    if cwd is None:
        return False
    if worktree_root is None:
        leaf = cwd.resolve().name
        return leaf.startswith("task-") or leaf.endswith("-pr-feedback")
    try:
        rel = cwd.resolve().relative_to(worktree_root.resolve())
    except ValueError:
        return False
    if not rel.parts:
        return False
    leaf = rel.parts[0]
    return leaf.startswith("task-") or leaf.endswith("-pr-feedback")
