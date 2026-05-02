"""Automation orchestrator (C4).

Reads new events from `events`, finds automations subscribed to the
trigger, creates a `Run`, prepares a worktree + per-run MCP config, and
launches the agent. Runs as a long-lived asyncio task alongside listeners
in `foundry serve`.

The orchestrator has two ways to discover work:

1. **DB poll** every `db_poll_sec` — durable, picks up events even if the
   in-process queue is full or after a restart.
2. **In-process hint** via `hint(event_id)` — listeners call this right
   after `record_external_event` so the orchestrator wakes immediately.
"""

from __future__ import annotations

import asyncio
import collections
import time
from pathlib import Path
from typing import Any

import structlog

from foundry import state, worktree
from foundry.agents.base import AgentStage, AgentTask
from foundry.agents.config import AgentSettings
from foundry.agents.factory import make_agent
from foundry.automations.registry import (
    Automation,
    automations_for_trigger,
    get_automation,
)
from foundry.config import Settings
from foundry.events import stage_span
from foundry.mcp.config import (
    build_mcp_config,
    mcp_config_path_for_run,
    write_mcp_config,
)
from foundry.models import Event, FailureKind, RunStatus
from foundry.session import compute_session_id

log = structlog.get_logger(__name__)


class Orchestrator:
    def __init__(self, settings: Settings, *, db_poll_sec: float = 0.5) -> None:
        self.settings = settings
        self.db_poll_sec = db_poll_sec
        self._queue: asyncio.Queue[int] = asyncio.Queue()
        self._dispatch_lock = asyncio.Lock()

    def hint(self, event_id: int) -> None:
        """Wake the orchestrator early. Best-effort — drops on full queue."""
        try:
            self._queue.put_nowait(event_id)
        except asyncio.QueueFull:
            pass

    async def run_forever(self, stop: asyncio.Event) -> None:
        cursor = await asyncio.to_thread(
            state.get_orchestrator_cursor, self.settings.db_path
        )
        while not stop.is_set():
            try:
                await asyncio.wait_for(self._queue.get(), timeout=self.db_poll_sec)
            except asyncio.TimeoutError:
                pass
            events = await asyncio.to_thread(
                state.read_events_after,
                self.settings.db_path,
                after_id=cursor,
                limit=100,
            )
            for ev in events:
                try:
                    await self.handle_event(ev)
                except Exception:
                    log.exception("orchestrator.handle_event_failed", event_id=ev.id)
                cursor = ev.id
                await asyncio.to_thread(
                    state.set_orchestrator_cursor, self.settings.db_path, cursor
                )

            # Pick up runs the API created with status=PENDING (e.g. retries).
            await self._pickup_pending_runs()

    async def _pickup_pending_runs(self) -> None:
        """Promote PENDING runs (created by the API for retry) to RUNNING.

        Wrapped in `_dispatch_lock` to serialize against `handle_event` —
        otherwise an event arriving for the same (event_id, automation_id)
        as a pending retry could spawn a parallel run before our flip
        from PENDING → RUNNING is visible.
        """
        async with self._dispatch_lock:
            pending_runs = await asyncio.to_thread(
                state.list_runs,
                self.settings.db_path,
                status=RunStatus.PENDING,
                limit=20,
            )
            for run in pending_runs:
                if run.id is None:
                    continue
                automation = get_automation(run.automation_id)
                event = await asyncio.to_thread(
                    state.get_event, self.settings.db_path, run.event_id
                )
                if automation is None or event is None:
                    # Don't leave the run hanging in PENDING forever — fail it
                    # with infra so the UI can surface the broken state.
                    log.warning(
                        "orchestrator.pending_run_missing_dep",
                        run_id=run.id,
                        automation_id=run.automation_id,
                        event_id=run.event_id,
                    )
                    await asyncio.to_thread(
                        state.finish_run,
                        self.settings.db_path,
                        run.id,
                        status=RunStatus.FAILED,
                        duration_sec=0.0,
                        failure_kind=FailureKind.INFRA,
                        failure_msg="automation or event missing at pickup",
                    )
                    continue
                # Flip to RUNNING only after we have everything we need —
                # avoids stranding the run in RUNNING with nothing executing.
                await asyncio.to_thread(
                    state.update_run,
                    self.settings.db_path,
                    run.id,
                    status=RunStatus.RUNNING,
                )
                asyncio.create_task(
                    self.execute_run(
                        run_id=run.id,
                        automation=automation,
                        event=event,
                        session_id=run.session_id,
                    ),
                    name=f"run:{run.id}",
                )

    async def handle_event(self, event: Event) -> list[int]:
        triggers = _trigger_ids_for_event(event)
        run_ids: list[int] = []
        async with self._dispatch_lock:
            for trigger_id in triggers:
                for automation in automations_for_trigger(trigger_id):
                    existing = await asyncio.to_thread(
                        state.find_running_run,
                        self.settings.db_path,
                        event_id=event.id,
                        automation_id=automation.id,
                    )
                    if existing is not None:
                        log.info(
                            "orchestrator.skip_duplicate_run",
                            run_id=existing.id,
                            automation_id=automation.id,
                            event_id=event.id,
                        )
                        continue
                    run_id = await self._create_and_dispatch(event, automation)
                    run_ids.append(run_id)
        return run_ids

    async def _create_and_dispatch(self, event: Event, automation: Automation) -> int:
        agent_backend = automation.agent.get("backend", "stub")
        session_id = compute_session_id(event.external_id, automation.id, agent_backend)
        session_seq = await asyncio.to_thread(
            state.next_session_seq, self.settings.db_path, session_id
        )
        run_id = await asyncio.to_thread(
            state.create_run,
            self.settings.db_path,
            automation_id=automation.id,
            event_id=event.id,
            session_id=session_id,
            session_seq=session_seq,
            status=RunStatus.RUNNING,
        )
        # Fire-and-forget — the run lives past handle_event() returning.
        asyncio.create_task(
            self.execute_run(
                run_id=run_id,
                automation=automation,
                event=event,
                session_id=session_id,
            ),
            name=f"run:{run_id}",
        )
        return run_id

    async def execute_run(
        self,
        *,
        run_id: int,
        automation: Automation,
        event: Event,
        session_id: str,
    ) -> None:
        db = self.settings.db_path
        started = time.monotonic()
        result: Any = None
        agent: Any = None
        task: AgentTask | None = None
        try:
            with stage_span(
                db,
                run_id=run_id,
                stage="run",
                input={"automation_id": automation.id, "session_id": session_id},
            ) as finish_stage:
                worktree_path, branch_name = await self._prepare_worktree(
                    automation, run_id
                )
                extra_env = self._extra_env(event, worktree_path, branch_name)
                cfg = build_mcp_config(
                    db_path=db,
                    run_id=run_id,
                    automation_id=automation.id,
                    skills=automation.skills,
                    extra_env=extra_env,
                )
                cfg_path = mcp_config_path_for_run(self.settings.worktree_root, run_id)
                write_mcp_config(cfg_path, cfg)

                # Resume the agent's CLI session when retrying. A retry-run
                # is fresh, but earlier runs sharing the same `session_id`
                # may already carry an `agent_session_id` we can resume.
                resume_session_id = await asyncio.to_thread(
                    _find_resume_session_id, db, session_id, run_id
                )
                agent_settings = AgentSettings(
                    stage=AgentStage.IMPLEMENT,
                    backend=automation.agent.get("backend", "stub"),
                    model=automation.agent.get("model") or "haiku",
                    db_path=db,
                    mcp_config=cfg_path,
                    resume_session_id=resume_session_id,
                )
                agent = make_agent(agent_settings)
                prompt = _load_automation_prompt(automation, event)
                task = AgentTask(
                    id=run_id,
                    title=f"automation:{automation.id}",
                    description=prompt,
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
                # Agent did not call mark_done / mark_failed — flag UNCLEAR.
                duration = time.monotonic() - started
                await asyncio.to_thread(
                    state.finish_run,
                    db,
                    run_id,
                    status=RunStatus.UNCLEAR,
                    duration_sec=duration,
                    cost_usd=getattr(result, "cost_usd", None),
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
            log.exception("orchestrator.execute_run_failed", run_id=run_id)
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

    async def _prepare_worktree(
        self, automation: Automation, run_id: int
    ) -> tuple[Path, str]:
        """Return (worktree_path, branch_name) for this run.

        When the automation declares `open_worktree`, we materialise a real
        git worktree on a fresh `foundry/task-{run_id}` branch and return its
        path/branch. Otherwise — placeholder dir without git, with a branch
        name that exists only as an env var (no git operations expected).
        """
        if "open_worktree" in automation.skills:
            await asyncio.to_thread(
                worktree.ensure_base_repo,
                self.settings.worktree_root,
                self.settings.source_repo,
            )
            wt_path, branch = await asyncio.to_thread(
                worktree.create_worktree, self.settings.worktree_root, run_id
            )
            return wt_path, branch
        path = self.settings.worktree_root / f"run-{run_id}"
        path.mkdir(parents=True, exist_ok=True)
        return path, f"foundry/run-{run_id}"

    def _extra_env(
        self, event: Event, worktree_path: Path, branch_name: str
    ) -> dict[str, str]:
        env: dict[str, str] = {
            "FOUNDRY_WORKTREE": str(worktree_path),
            "FOUNDRY_BRANCH": branch_name,
            "FOUNDRY_WORKTREE_ROOT": str(self.settings.worktree_root),
            "FOUNDRY_SOURCE_REPO": self.settings.source_repo,
            "FOUNDRY_TARGET_REPO": self.settings.target_repo,
        }
        if event.source == "github_issues":
            number = (event.payload or {}).get("number")
            if number is not None:
                env["FOUNDRY_ISSUE_NUMBER"] = str(number)
        return env


def _find_resume_session_id(
    db_path: Path, session_id: str, current_run_id: int
) -> str | None:
    """Return the agent_session_id from the most recent prior run sharing
    `session_id`, or None if there is no prior run with one. Excludes the
    current run."""
    runs = state.list_runs(db_path, limit=200)
    for r in runs:
        if r.id == current_run_id:
            continue
        if r.session_id != session_id:
            continue
        if r.agent_session_id:
            return r.agent_session_id
    return None


def _trigger_ids_for_event(event: Event) -> list[str]:
    if event.source == "cron":
        rule_id = (event.payload or {}).get("rule_id")
        return [f"cron:{rule_id}"] if rule_id else []
    return [event.source]


def _load_automation_prompt(automation: Automation, event: Event) -> str:
    if not automation.prompt_path:
        return automation.description
    p = Path(automation.prompt_path)
    if not p.is_absolute():
        # Treat as relative to the foundry package's automations/ dir.
        p = Path(__file__).parent / "automations" / automation.prompt_path
    if not p.exists():
        return automation.description
    template = p.read_text(encoding="utf-8")
    payload = event.payload or {}
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
