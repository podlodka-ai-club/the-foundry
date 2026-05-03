from __future__ import annotations

import sys
import time

import click
import structlog

from . import pipeline, state, workflows
from .config import ConfigError, load_settings
from .models import Stage, TaskStatus


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


@main.command("run-issue")
@click.argument("number", type=int)
def run_issue(number: int) -> None:
    """Run one GitHub issue now, bypassing the polling queue filters."""
    try:
        settings = load_settings()
    except ConfigError as e:
        click.echo(f"config error: {e}", err=True)
        sys.exit(2)

    task = pipeline.run_issue(settings, number)
    click.echo(
        f"#{task.issue_number:>4}  {task.status.value:<8}  {task.current_stage.value:<10}  {task.pr_url or '-'}"
    )


@main.command("pr-feedback")
@click.option("--once", is_flag=True, help="Run a single PR feedback pass and exit.")
@click.option(
    "--interval",
    type=int,
    default=None,
    help="Poll interval in seconds (overrides POLL_INTERVAL_SECONDS).",
)
def pr_feedback(once: bool, interval: int | None) -> None:
    """Apply review / CI feedback on open Foundry PR branches.

    By default runs forever, polling open Foundry PRs every
    POLL_INTERVAL_SECONDS. Pass --once for a single pass.
    """
    try:
        settings = load_settings()
    except ConfigError as e:
        click.echo(f"config error: {e}", err=True)
        sys.exit(2)

    sleep_s = interval if interval is not None else settings.poll_interval_seconds
    log = structlog.get_logger()

    def _one_pass() -> None:
        processed = workflows.pr_feedback_once(settings)
        if not processed:
            return
        for task in processed:
            click.echo(
                f"#{task.issue_number:>4}  {task.status.value:<8}  {task.current_stage.value:<10}  {task.pr_url or '-'}"
            )

    if once:
        _one_pass()
        return

    click.echo(f"foundry pr-feedback: polling every {sleep_s}s (Ctrl+C to stop)")
    try:
        while True:
            try:
                _one_pass()
            except Exception:
                log.exception("pr_feedback.pass_failed")
            time.sleep(sleep_s)
    except KeyboardInterrupt:
        click.echo("foundry pr-feedback: stopped")


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


if __name__ == "__main__":
    main()
