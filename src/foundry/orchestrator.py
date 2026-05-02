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
import time
from pathlib import Path
from typing import Any

import structlog

from foundry import state, worktree
from foundry.agents.base import AgentStage, AgentTask
from foundry.agents.config import AgentSettings
from foundry.agents.factory import make_agent
from foundry.automations.registry import Automation, automations_for_trigger
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
                worktree_path = await self._prepare_worktree(automation, run_id)
                branch_name = f"foundry/run-{run_id}"

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

                agent_settings = AgentSettings(
                    stage=AgentStage.IMPLEMENT,
                    backend=automation.agent.get("backend", "stub"),
                    model=automation.agent.get("model") or "haiku",
                    db_path=db,
                    mcp_config=cfg_path,
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

    async def _prepare_worktree(self, automation: Automation, run_id: int) -> Path:
        if "open_worktree" in automation.skills:
            await asyncio.to_thread(
                worktree.ensure_base_repo,
                self.settings.worktree_root,
                self.settings.source_repo,
            )
            wt_path, _branch = await asyncio.to_thread(
                worktree.create_worktree, self.settings.worktree_root, run_id
            )
            return wt_path
        path = self.settings.worktree_root / f"run-{run_id}"
        path.mkdir(parents=True, exist_ok=True)
        return path

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
    try:
        return template.format_map(
            {
                **payload,
                "title": payload.get("title", ""),
                "body": payload.get("body", ""),
            }
        )
    except Exception:
        return template
