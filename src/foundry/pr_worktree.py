"""Per-PR worktree helpers for the ``pr_review`` automation.

The user keeps multiple separate git checkouts under one umbrella folder
(``~/w/datura/lium/main``) — that umbrella is itself **not** a git repo.
For each PR we materialize an isolated worktree from the matching local
checkout at the PR's head SHA, then ``rsync`` an overlay of untracked
``CLAUDE.md`` / ``.claude`` / ``.agents`` so Claude Code sees the same
project conventions the developer has locally.

The worktree is placed as a sibling of the umbrella's subrepos so Claude
Code's CLAUDE.md walk-up automatically picks up the umbrella-level file.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

import structlog

from . import shell

log = structlog.get_logger(__name__)


class PrWorktreeError(RuntimeError):
    """Raised when discovery / setup / cleanup cannot proceed."""


def discover_repos(base: Path) -> dict[str, Path]:
    """Return ``{owner/name: local_path}`` for git repos under ``base``.

    Scans depth ≤ 2 (direct children + one nested level) — enough to cover
    the umbrella's ``chutes/chutes-miner`` style layouts without descending
    into ``node_modules`` / ``.venv`` / submodule trees.
    """
    result: dict[str, Path] = {}
    if not base.exists() or not base.is_dir():
        return result

    candidates: list[Path] = []
    for child in base.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / ".git").exists():
            candidates.append(child)
            continue
        # one level deeper for owner/repo style nesting (chutes/chutes-miner)
        try:
            for grand in child.iterdir():
                if (
                    grand.is_dir()
                    and not grand.name.startswith(".")
                    and (grand / ".git").exists()
                ):
                    candidates.append(grand)
        except (PermissionError, OSError):
            continue

    for path in candidates:
        slug = _origin_slug(path)
        if slug:
            result[slug] = path
    return result


def _origin_slug(repo: Path) -> str | None:
    """Read ``git remote get-url origin`` and normalize to ``owner/name``."""
    res = shell.run(
        ["git", "remote", "get-url", "origin"], cwd=repo, check=False
    )
    if not res.ok:
        return None
    return _normalize_slug(res.stdout.strip())


def _normalize_slug(url: str) -> str | None:
    """``git@github.com:owner/name.git`` → ``owner/name``.

    Handles both SSH (``git@host:owner/name``) and HTTPS
    (``https://host/owner/name[.git]``) forms; trailing ``.git`` stripped.
    """
    if not url:
        return None
    cleaned = url.strip()
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    if cleaned.startswith("git@"):
        # git@host:owner/name → owner/name
        _, _, tail = cleaned.partition(":")
        cleaned = tail
    elif "://" in cleaned:
        # https://host/owner/name → owner/name
        _, _, tail = cleaned.partition("://")
        _, _, tail = tail.partition("/")
        cleaned = tail
    parts = cleaned.split("/")
    if len(parts) < 2:
        return None
    return f"{parts[-2]}/{parts[-1]}"


def _target_path(base_path: Path, run_id: int, repo: str) -> Path:
    repo_short = repo.split("/")[-1]
    return base_path / f"_foundry-pr-{run_id}-{repo_short}"


def prepare_pr_worktree(
    *,
    base_path: Path,
    repo: str,
    head_sha: str,
    run_id: int,
) -> tuple[Path, str, Callable[[], None]]:
    """Materialize ``base_path/_foundry-pr-<run_id>-<repo>`` at ``head_sha``.

    Steps:
      1. Discover the matching local checkout for ``repo`` under ``base_path``.
      2. ``git fetch origin <head_sha>`` in that checkout.
      3. ``git worktree add --detach`` into the target path.
      4. ``rsync`` the user's untracked ``*.md`` / ``.claude/`` / ``.agents/``
         on top so Claude Code sees the same local conventions.

    Returns ``(worktree_path, branch_label, cleanup_fn)``. ``branch_label``
    is the short SHA — there is no real branch since the worktree is
    detached. ``cleanup_fn`` removes both the git worktree registration and
    any leftover files.
    """
    repos = discover_repos(base_path)
    base = repos.get(repo)
    if base is None:
        raise PrWorktreeError(
            f"no local checkout for {repo} under {base_path}"
        )

    target = _target_path(base_path, run_id, repo)
    if target.exists():
        # Stale leftovers from an earlier crash — best-effort wipe.
        _cleanup(base, target)

    shell.run(["git", "fetch", "origin", head_sha], cwd=base)
    shell.run(
        ["git", "worktree", "add", "--detach", str(target), head_sha],
        cwd=base,
    )

    # Overlay developer's untracked notes/configs. ``--include='*/'`` lets
    # rsync recurse; the leaf includes pick what we copy; ``--exclude='*'``
    # drops everything else. Secrets like ``.env`` are NOT in the include
    # list, so they're filtered out.
    shell.run(
        [
            "rsync", "-a",
            "--include=*/",
            "--include=*.md",
            "--include=.claude/***",
            "--include=.agents/***",
            "--exclude=*",
            f"{base}/",
            f"{target}/",
        ],
        check=False,
    )

    def cleanup() -> None:
        _cleanup(base, target)

    return target, head_sha[:12], cleanup


def _cleanup(base: Path, target: Path) -> None:
    """Remove the git worktree registration and any leftover dir contents."""
    res = shell.run(
        ["git", "worktree", "remove", "--force", str(target)],
        cwd=base,
        check=False,
    )
    if not res.ok:
        log.info(
            "pr_worktree.cleanup.git_remove_failed",
            target=str(target),
            stderr=res.stderr[:200],
        )
    if target.exists():
        try:
            shutil.rmtree(target)
        except OSError as exc:
            log.warning(
                "pr_worktree.cleanup.rmtree_failed",
                target=str(target),
                error=repr(exc),
            )


__all__ = [
    "PrWorktreeError",
    "discover_repos",
    "prepare_pr_worktree",
]
