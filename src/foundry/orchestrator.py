"""Automation orchestrator — the loop that drives runs.

PENDING runs are the only queue. Listeners enqueue work via
:func:`foundry.events.dispatch_event` (which inserts the event AND a
``PENDING`` run for every subscribed automation in one transaction). This
loop atomically flips the oldest PENDING run to RUNNING and hands it to
:mod:`foundry.runner` for execution.

The dispatcher is woken by :class:`asyncio.Event` (set on each successful
dispatch from CLI's emit wrapper) or by a periodic timeout — whichever
comes first.
"""

from __future__ import annotations

import asyncio

import structlog

from foundry import runner, state
from foundry.automations.registry import Automation, get_automation
from foundry.config import Settings
from foundry.models import Event, FailureKind, Run, RunStatus

log = structlog.get_logger(__name__)


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        *,
        db_poll_sec: float = 0.5,
        wake: asyncio.Event | None = None,
    ) -> None:
        self.settings = settings
        self.db_poll_sec = db_poll_sec
        self.wake = wake or asyncio.Event()

    async def run_forever(self, stop: asyncio.Event) -> None:
        """Recover orphan RUNNING rows, then loop: drain PENDING → wait."""
        recovered = await asyncio.to_thread(
            state.recover_orphan_runs, self.settings.db_path
        )
        if recovered:
            log.info("orchestrator.recovered_orphan_runs", count=recovered)

        while not stop.is_set():
            # Clear BEFORE draining — any wake signalled while draining is
            # captured by the next wait_for and triggers another drain pass.
            self.wake.clear()
            await self._drain_pending()
            try:
                await asyncio.wait_for(self.wake.wait(), timeout=self.db_poll_sec)
            except asyncio.TimeoutError:
                pass

    async def _drain_pending(self) -> None:
        while True:
            run = await asyncio.to_thread(
                state.claim_pending_run, self.settings.db_path
            )
            if run is None:
                return
            asyncio.create_task(
                self._execute_claimed(run),
                name=f"run:{run.id}",
            )

    async def _execute_claimed(self, run: Run) -> None:
        """Resolve automation + event for a claimed run, then execute it.

        If either lookup fails (automation deregistered, event vanished) the
        run is finalized as FAILED/INFRA so it never sticks in RUNNING.
        """
        if run.id is None:
            return
        automation = get_automation(run.automation_id)
        event = await asyncio.to_thread(
            state.get_event, self.settings.db_path, run.event_id
        )
        if automation is None or event is None:
            log.warning(
                "orchestrator.claim_missing_dep",
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
                failure_msg="automation or event missing at claim",
            )
            return
        await self.execute_run(
            run_id=run.id,
            automation=automation,
            event=event,
            session_id=run.session_id,
        )

    async def execute_run(
        self,
        *,
        run_id: int,
        automation: Automation,
        event: Event,
        session_id: str,
    ) -> None:
        """Thin wrapper for tests that drive a run with a pre-resolved
        automation + event (skipping the queue). Production paths go through
        :meth:`_execute_claimed`. Real work lives in
        :func:`foundry.runner.execute_run`.
        """
        await runner.execute_run(
            settings=self.settings,
            run_id=run_id,
            automation=automation,
            event=event,
            session_id=session_id,
        )
