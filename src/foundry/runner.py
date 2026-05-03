"""Per-run executor: turns one (claimed) Run + Automation + Event into a
finished agent invocation.

The orchestrator owns the loop (``recover_orphans → claim → execute → wait``);
this module owns the body of ``execute``: workspace prep, MCP-config write,
agent spawn, ``STATUS:`` parse, terminal ``finish_run``. Pure functions,
no state of its own — everything comes in through arguments.
"""

from __future__ import annotations

import asyncio
import collections
import time
from pathlib import Path
from typing import Any, Callable

import structlog

from foundry import pr_worktree, state, worktree
from foundry.agents.base import AgentTask
from foundry.agents.config import AgentSettings
from foundry.agents.factory import make_agent
from foundry.automations.registry import Automation
from foundry.config import Settings
from foundry.events import record_event, stage_span
from foundry.mcp.config import (
    build_mcp_config,
    mcp_config_path_for_run,
    write_mcp_config,
)
from foundry.models import Event, FailureKind, RunStatus
from foundry.status_marker import parse_status_marker

log = structlog.get_logger(__name__)


async def execute_run(
    *,
    settings: Settings,
    run_id: int,
    automation: Automation,
    event: Event,
    session_id: str,
) -> None:
    """Run one already-claimed run to completion.

    Writes a ``stage="run"`` span around the agent invocation, parses the
    terminal ``STATUS:`` marker from the agent's response, and finalises
    the row in ``runs``. Any exception is caught and turned into
    ``FAILED/INFRA`` so the run never sticks in ``RUNNING``.
    """
    db = settings.db_path
    started = time.monotonic()
    result: Any = None
    agent: Any = None
    task: AgentTask | None = None
    cleanup_fn: Callable[[], None] | None = None
    try:
        with stage_span(
            db,
            run_id=run_id,
            stage="run",
            input={"automation_id": automation.id, "session_id": session_id},
        ) as finish_stage:
            worktree_path, branch_name, prepared_cleanup = (
                await _prepare_workspace(settings, automation, event, run_id)
            )
            cleanup_fn = prepared_cleanup
            extra_env = _extra_env(
                settings, event, automation, worktree_path, branch_name
            )
            cfg = build_mcp_config(
                db_path=db,
                run_id=run_id,
                automation_id=automation.id,
                extra_env=extra_env,
            )
            cfg_path = mcp_config_path_for_run(settings.worktree_root, run_id)
            write_mcp_config(cfg_path, cfg)

            # Resume the agent's CLI session when a prior DONE run in this
            # same `session_id` left a clean session id behind.
            # `_find_resume_session_id` filters to status=DONE so we never
            # piggyback on a stuck/failed CLI session.
            resume_session_id = await asyncio.to_thread(
                _find_resume_session_id, db, session_id, run_id
            )
            agent_settings = AgentSettings(
                backend=automation.agent.get("backend", "stub"),
                model=automation.agent.get("model") or "haiku",
                db_path=db,
                mcp_config=cfg_path,
                resume_session_id=resume_session_id,
            )
            agent = make_agent(agent_settings)
            prompt = _load_automation_prompt(
                automation, event, resuming=resume_session_id is not None
            )
            task = AgentTask(
                id=run_id,
                title=f"automation:{automation.id}",
                description=prompt,
            )

            # Record exactly what we're feeding the agent so the UI can
            # show the actual prompt (raw template + interpolated event
            # context). Truncated to 64KB by record_event.
            record_event(
                db,
                run_id=run_id,
                stage="run",
                kind="agent_input",
                payload={
                    "prompt": prompt,
                    "backend": agent_settings.backend,
                    "model": agent_settings.model,
                    "resume_session_id": resume_session_id,
                },
            )

            result = await asyncio.to_thread(
                agent.apply, task, worktree_path, prompt
            )
            finish_stage(
                output={"summary": getattr(result, "result", "") or ""},
                cost_usd=getattr(result, "cost_usd", None),
                tokens_in=getattr(result, "tokens_in", None),
                tokens_out=getattr(result, "tokens_out", None),
            )

        run_now = await asyncio.to_thread(state.get_run, db, run_id)
        if run_now is not None and run_now.status is RunStatus.RUNNING:
            # Final status comes from the agent's terminal STATUS: marker
            # (parsed from `result.response`). No marker → UNCLEAR.
            duration = time.monotonic() - started
            parsed = parse_status_marker(getattr(result, "response", "") or "")
            if parsed is None:
                await asyncio.to_thread(
                    state.finish_run,
                    db,
                    run_id,
                    status=RunStatus.UNCLEAR,
                    duration_sec=duration,
                    cost_usd=getattr(result, "cost_usd", None),
                )
            else:
                final_status, kind, outcome = parsed
                await asyncio.to_thread(
                    state.finish_run,
                    db,
                    run_id,
                    status=final_status,
                    duration_sec=duration,
                    cost_usd=getattr(result, "cost_usd", None),
                    failure_kind=kind,
                    failure_msg=(
                        None
                        if final_status is RunStatus.DONE
                        else f"agent reported {kind.value if kind else 'unclear'}"
                    ),
                    outcome=outcome,
                )

        agent_session: str | None = None
        if agent is not None and task is not None:
            try:
                agent_session = agent.get_session_id(task)
            except Exception:
                agent_session = None
        if agent_session:
            await asyncio.to_thread(
                state.update_run, db, run_id, agent_session_id=agent_session
            )
    except Exception as exc:  # noqa: BLE001 — surface as failed run
        log.exception("runner.execute_run_failed", run_id=run_id)
        duration = time.monotonic() - started
        await asyncio.to_thread(
            state.finish_run,
            db,
            run_id,
            status=RunStatus.FAILED,
            duration_sec=duration,
            failure_kind=FailureKind.INFRA,
            failure_msg=repr(exc),
        )
    finally:
        if cleanup_fn is not None:
            try:
                await asyncio.to_thread(cleanup_fn)
            except Exception:
                log.exception(
                    "runner.worktree_cleanup_failed", run_id=run_id
                )


# ---------------------------------------------------------------------------
# Workspace selection
# ---------------------------------------------------------------------------


async def _prepare_workspace(
    settings: Settings,
    automation: Automation,
    event: Event,
    run_id: int,
) -> tuple[Path, str, Callable[[], None] | None]:
    """Return ``(cwd_path, branch_name, cleanup_fn)`` for this run.

    Dispatched on ``automation.workspace`` (see ``Automation`` docstring).
    The ``branch_name`` for non-git modes is a synthetic placeholder so
    env vars (``FOUNDRY_BRANCH``) stay populated for skills that read them.
    """
    match automation.workspace:
        case "git_worktree":
            await asyncio.to_thread(
                worktree.ensure_base_repo,
                settings.worktree_root,
                settings.source_repo,
            )
            wt_path, branch = await asyncio.to_thread(
                worktree.create_worktree, settings.worktree_root, run_id
            )
            return wt_path, branch, None
        case "pr_worktree":
            return await _prepare_pr_worktree(settings, event, run_id)
        case "fixed":
            # cwd presence is validated in Automation.__post_init__.
            assert automation.cwd is not None
            path = automation.cwd.expanduser()
            path.mkdir(parents=True, exist_ok=True)
            return path, f"foundry/run-{run_id}", None
        case "ephemeral":
            path = settings.worktree_root / f"run-{run_id}"
            path.mkdir(parents=True, exist_ok=True)
            return path, f"foundry/run-{run_id}", None
        case _:
            raise ValueError(
                f"automation {automation.id!r}: unknown workspace "
                f"{automation.workspace!r}"
            )


async def _prepare_pr_worktree(
    settings: Settings, event: Event, run_id: int
) -> tuple[Path, str, Callable[[], None]]:
    base_path = settings.pr_review_base_path
    if base_path is None:
        raise pr_worktree.PrWorktreeError(
            "pr_review_base_path is not configured (set PR_REVIEW_BASE_PATH)"
        )
    payload = event.payload or {}
    repo = payload.get("repo")
    head_sha = payload.get("head_sha")
    if not repo or not head_sha:
        raise pr_worktree.PrWorktreeError(
            f"event {event.id} payload missing repo/head_sha for pr_worktree"
        )
    return await asyncio.to_thread(
        pr_worktree.prepare_pr_worktree,
        base_path=base_path,
        repo=repo,
        head_sha=head_sha,
        run_id=run_id,
    )


# ---------------------------------------------------------------------------
# Env passed to the agent's MCP subprocess
# ---------------------------------------------------------------------------


def _extra_env(
    settings: Settings,
    event: Event,
    automation: Automation,
    worktree_path: Path,
    branch_name: str,
) -> dict[str, str]:
    env: dict[str, str] = {
        "FOUNDRY_WORKTREE": str(worktree_path),
        "FOUNDRY_BRANCH": branch_name,
        "FOUNDRY_WORKTREE_ROOT": str(settings.worktree_root),
        "FOUNDRY_SOURCE_REPO": settings.source_repo,
        "FOUNDRY_TARGET_REPO": settings.target_repo,
    }
    if event.source == "github_issues":
        number = (event.payload or {}).get("number")
        if number is not None:
            env["FOUNDRY_ISSUE_NUMBER"] = str(number)
    if event.source == "telegram":
        chat_id = (event.payload or {}).get("chat_id")
        if chat_id is not None:
            env["FOUNDRY_TG_CHAT_ID"] = str(chat_id)
        # Forward the bot token so telegram_reply skill can call
        # sendMessage from inside the MCP subprocess.
        if settings.telegram_bot_token:
            env["TELEGRAM_BOT_TOKEN"] = settings.telegram_bot_token
    if automation.workspace == "pr_worktree" and event.source == "github_pr_review":
        payload = event.payload or {}
        for key, var in (
            ("repo", "FOUNDRY_PR_REPO"),
            ("head_sha", "FOUNDRY_PR_HEAD_SHA"),
            ("number", "FOUNDRY_PR_NUMBER"),
            ("url", "FOUNDRY_PR_URL"),
            ("author", "FOUNDRY_PR_AUTHOR"),
        ):
            value = payload.get(key)
            if value is not None:
                env[var] = str(value)
        if settings.pr_review_base_path is not None:
            env["PR_REVIEW_BASE_PATH"] = str(settings.pr_review_base_path)
    return env


# ---------------------------------------------------------------------------
# Session resume + prompt rendering
# ---------------------------------------------------------------------------


def _find_resume_session_id(
    db_path: Path, session_id: str, current_run_id: int
) -> str | None:
    """Return the agent_session_id from the most recent prior **successful**
    run sharing ``session_id``, or None.

    Resuming a stuck/aborted CLI session (UNCLEAR/FAILED) drags its broken
    state into the new turn — e.g. an unanswered "do you want to send? (y/n)"
    prompt that swallows the next user input. Only DONE runs leave the CLI
    session in a clean "ready for the next turn" state.
    """
    runs = state.list_runs(db_path, limit=200)
    for r in runs:
        if r.id == current_run_id:
            continue
        if r.session_id != session_id:
            continue
        if r.status is not RunStatus.DONE:
            continue
        if r.agent_session_id:
            return r.agent_session_id
    return None


def _load_automation_prompt(
    automation: Automation, event: Event, *, resuming: bool = False
) -> str:
    """Render the prompt fed to the agent for one event.

    On ``resuming=True``, we're continuing an existing CLI session that
    already saw the full template on its first turn. For chat-style sources
    (Telegram), pass only the new user message — re-rendering the full
    system prompt would bloat the input and confuse the model. For other
    sources we still re-render the template (retry semantics — same
    instructions, same payload, fresh attempt).
    """
    payload = event.payload or {}
    if resuming and event.source == "telegram":
        return str(payload.get("text", ""))

    if not automation.prompt_path:
        return automation.description
    p = Path(automation.prompt_path)
    if not p.is_absolute():
        # Treat as relative to the foundry package's automations/ dir.
        p = Path(__file__).parent / "automations" / automation.prompt_path
    if not p.exists():
        return automation.description
    template = p.read_text(encoding="utf-8")
    ctx: dict[str, Any] = collections.defaultdict(str, {
        "title": payload.get("title", ""),
        "body": payload.get("body", ""),
        "repo": payload.get("repo", ""),
        "number": payload.get("number", ""),
        "labels": ", ".join(payload.get("labels") or []),
        **payload,
    })
    try:
        return template.format_map(ctx)
    except Exception:
        return template
