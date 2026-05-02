from __future__ import annotations

import asyncio
import random
import signal
import sys
import time
from pathlib import Path
from typing import Any

import click
import structlog

from . import pipeline, state
from .config import ConfigError, Settings, load_settings
from .listeners import EmitFn, Listener, build_listeners
from .models import Stage, TaskStatus
from .orchestrator import Orchestrator
from .state import record_external_event

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
@click.option("--once", is_flag=True, help="Run a single pass and exit (legacy behaviour).")
@click.option(
    "--interval",
    type=int,
    default=None,
    help="Poll interval in seconds (overrides POLL_INTERVAL_SECONDS).",
)
def run(once: bool, interval: int | None) -> None:
    """Fetch labeled issues and drive each through the pipeline.

    By default runs forever, polling GitHub every POLL_INTERVAL_SECONDS.
    Pass --once for a single pass (the old behaviour).
    """
    try:
        settings = load_settings()
    except ConfigError as e:
        click.echo(f"config error: {e}", err=True)
        sys.exit(2)

    sleep_s = interval if interval is not None else settings.poll_interval_seconds
    log = structlog.get_logger()

    def _one_pass() -> None:
        processed = pipeline.run_once(settings)
        for task in processed:
            click.echo(
                f"#{task.issue_number:>4}  {task.status.value:<8}  {task.current_stage.value:<10}  {task.pr_url or '-'}"
            )

    if once:
        _one_pass()
        return

    click.echo(f"foundry: polling every {sleep_s}s (Ctrl+C to stop)")
    try:
        while True:
            try:
                _one_pass()
            except Exception:
                log.exception("run.pass_failed")
            time.sleep(sleep_s)
    except KeyboardInterrupt:
        click.echo("foundry: stopped")


@main.command()
def status() -> None:
    """Print all tasks currently in the database."""
    try:
        settings = load_settings()
    except ConfigError as e:
        click.echo(f"config error: {e}", err=True)
        sys.exit(2)

    state.init_db(settings.db_path)
    tasks = state.list_tasks(settings.db_path)
    if not tasks:
        click.echo("no tasks yet")
        return

    click.echo(f"{'id':>3}  {'issue':>6}  {'status':<8}  {'stage':<10}  pr")
    for t in tasks:
        click.echo(
            f"{t.id:>3}  {t.issue_number:>6}  {t.status.value:<8}  {t.current_stage.value:<10}  {t.pr_url or '-'}"
        )


@main.command()
@click.argument("task_id", type=int)
def reset(task_id: int) -> None:
    """Reset a task back to pending (for debugging reruns)."""
    try:
        settings = load_settings()
    except ConfigError as e:
        click.echo(f"config error: {e}", err=True)
        sys.exit(2)

    state.init_db(settings.db_path)
    task = state.get_task(settings.db_path, task_id)
    if task is None:
        click.echo(f"no task with id {task_id}", err=True)
        sys.exit(1)

    task.status = TaskStatus.PENDING
    task.current_stage = Stage.FETCH
    task.pr_url = None
    state.upsert_task(settings.db_path, task)
    click.echo(f"task {task_id} reset to pending")


def _make_emit(
    source: str,
    db_path: Path,
    orchestrator: Orchestrator | None = None,
) -> EmitFn:
    async def emit(
        *,
        external_id: str,
        kind: str,
        payload: dict[str, Any],
        parent_event_id: int | None = None,
    ) -> int | None:
        event_id = await asyncio.to_thread(
            record_external_event,
            db_path,
            source=source,
            external_id=external_id,
            kind=kind,
            payload=payload,
            parent_event_id=parent_event_id,
        )
        if orchestrator is not None and event_id is not None:
            orchestrator.hint(event_id)
        return event_id

    return emit


async def _supervise(
    listener: Listener,
    db_path: Path,
    stop: asyncio.Event,
    orchestrator: Orchestrator | None = None,
) -> None:
    """Run a listener with crash-loop backoff, exiting cleanly when ``stop`` fires."""
    backoff = 1.0
    while not stop.is_set():
        try:
            emit = _make_emit(listener.source, db_path, orchestrator)
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
    listeners = build_listeners(settings)
    log.info("serve.start", listener_ids=[l.id for l in listeners])

    if not listeners:
        log.info("serve.no_listeners_enabled")
        return

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            # Windows / non-main thread — caller will rely on Ctrl+C exception.
            pass

    orchestrator = Orchestrator(settings)
    tasks = [
        asyncio.create_task(
            _supervise(l, settings.db_path, stop, orchestrator),
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
