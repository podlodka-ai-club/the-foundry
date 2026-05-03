from __future__ import annotations

import asyncio
import random
import signal
import sys
from pathlib import Path
from typing import Any

import click
import structlog

from . import state, triggers
from .automations.registry import AUTOMATIONS
from .config import ConfigError, Settings, load_settings
from .events import dispatch_event
from .listeners import EmitFn, Listener, build_listeners
from .listeners.cron_rules import DEFAULT_CRON_RULES
from .models import RunStatus
from .orchestrator import Orchestrator

log = structlog.get_logger()


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )


@click.group()
def main() -> None:
    """The Foundry — agentic feature-pipeline orchestrator (skeleton)."""
    _configure_logging()


@main.command()
@click.option("--status", type=str, default=None, help="Filter by status (running/waiting/done/failed/unclear).")
@click.option("--limit", type=int, default=20, help="Max rows to print.")
def runs(status: str | None, limit: int) -> None:
    """List runs from DB."""
    try:
        settings = load_settings()
    except ConfigError as e:
        click.echo(f"config error: {e}", err=True)
        sys.exit(2)

    state.init_db(settings.db_path)
    rs = state.list_runs(
        settings.db_path,
        status=RunStatus(status) if status else None,
        limit=limit,
    )
    if not rs:
        click.echo("no runs yet")
        return
    click.echo(f"{'id':>4}  {'automation':<16}  {'status':<10}  {'session_id':<16}  failure")
    for r in rs:
        click.echo(
            f"{r.id:>4}  {r.automation_id:<16}  {r.status.value:<10}  "
            f"{r.session_id:<16}  {r.failure_kind.value if r.failure_kind else ''}"
        )


def _make_emit(db_path: Path, wake: asyncio.Event) -> EmitFn:
    """Listener-side emit: dispatch event and wake the orchestrator."""
    async def emit(
        *,
        trigger_id: str,
        dedupe_key: str,
        payload: dict[str, Any],
        parent_event_id: int | None = None,
    ) -> int | None:
        event_id = await asyncio.to_thread(
            dispatch_event,
            db_path,
            trigger_id=trigger_id,
            dedupe_key=dedupe_key,
            payload=payload,
            parent_event_id=parent_event_id,
        )
        if event_id is not None:
            wake.set()
        return event_id

    return emit


async def _supervise(
    listener: Listener,
    db_path: Path,
    stop: asyncio.Event,
    wake: asyncio.Event,
) -> None:
    """Run a listener with crash-loop backoff, exiting cleanly when ``stop`` fires."""
    backoff = 1.0
    while not stop.is_set():
        try:
            emit = _make_emit(db_path, wake)
            log.info("listener.start", listener=listener.id)
            await listener.listen(emit)
            log.info("listener.exited_clean", listener=listener.id)
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception(
                "listener.crashed", listener=listener.id, backoff=backoff
            )
            jitter = backoff * (0.8 + random.random() * 0.4)
            try:
                await asyncio.wait_for(stop.wait(), timeout=jitter)
                return
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, 60.0)


async def _serve_async(settings: Settings) -> None:
    cron_rule_ids = tuple(rule.id for rule in DEFAULT_CRON_RULES)
    triggers.validate_registry(AUTOMATIONS, known_cron_rule_ids=cron_rule_ids)

    listeners = build_listeners(settings)
    log.info("serve.start", listener_ids=[l.id for l in listeners])

    if not listeners:
        log.info("serve.no_listeners_enabled")
        return

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    wake = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            # Windows / non-main thread — caller will rely on Ctrl+C exception.
            pass

    orchestrator = Orchestrator(settings, wake=wake)
    tasks = [
        asyncio.create_task(
            _supervise(l, settings.db_path, stop, wake),
            name=f"listener:{l.id}",
        )
        for l in listeners
    ]
    tasks.append(
        asyncio.create_task(
            orchestrator.run_forever(stop),
            name="orchestrator",
        )
    )
    await stop.wait()
    log.info("serve.stopping")
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    log.info("serve.stopped")


@main.command()
def serve() -> None:
    """Run listeners as a long-lived asyncio daemon (writes events to DB)."""
    try:
        settings = load_settings()
    except ConfigError as e:
        click.echo(f"config error: {e}", err=True)
        sys.exit(2)

    state.init_db(settings.db_path)
    asyncio.run(_serve_async(settings))


if __name__ == "__main__":
    main()
