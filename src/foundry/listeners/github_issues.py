from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from .. import shell, triggers
from .base import EmitFn

log = structlog.get_logger(__name__)


class GithubIssuesListener:
    """Polls GitHub issues by label and emits one ``issue_opened`` event per
    open issue per tick. Dedup happens at the DB layer.
    """

    id = "github_issues"
    source = "github_issues"

    def __init__(self, *, repo: str, label: str, poll_sec: int = 30) -> None:
        self.repo = repo
        self.label = label
        self.poll_sec = poll_sec

    def _fetch_issues(self) -> list[dict[str, Any]]:
        result = shell.run(
            [
                "gh", "issue", "list",
                "--repo", self.repo,
                "--label", self.label,
                "--state", "open",
                "--json", "number,title,body,labels,createdAt,updatedAt",
                "--limit", "50",
            ]
        )
        return json.loads(result.stdout or "[]")

    async def _emit_one(self, emit: EmitFn, issue: dict[str, Any]) -> None:
        number = int(issue["number"])
        labels = [label["name"] for label in issue.get("labels") or []]
        payload = {
            "repo": self.repo,
            "number": number,
            "title": issue.get("title") or "",
            "body": issue.get("body") or "",
            "labels": labels,
            "created_at": issue.get("createdAt"),
            "updated_at": issue.get("updatedAt"),
            "short_name": f"#{number}",
        }
        await emit(
            trigger_id=triggers.GITHUB_ISSUE_OPENED,
            dedupe_key=f"{self.repo}#{number}",
            payload=payload,
        )

    async def tick_once(self, emit: EmitFn) -> None:
        """One poll tick: fetch issues + emit each. Public for tests."""
        issues = await asyncio.to_thread(self._fetch_issues)
        for issue in issues:
            await self._emit_one(emit, issue)

    async def listen(self, emit: EmitFn) -> None:
        while True:
            try:
                await self.tick_once(emit)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("listener.tick.error", listener=self.id)
            await asyncio.sleep(self.poll_sec)
