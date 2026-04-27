from __future__ import annotations

import sys

import click
import structlog

from . import pipeline, state
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
def run() -> None:
    """Fetch open issues and run each through the full pipeline once."""
    try:
        settings = load_settings()
    except ConfigError as e:
        click.echo(f"config error: {e}", err=True)
        sys.exit(2)

    processed = pipeline.run_once(settings)
    for task in processed:
        click.echo(
            f"#{task.issue_number:>4}  {task.status.value:<8}  {task.current_stage.value:<10}  {task.pr_url or '-'}"
        )


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
