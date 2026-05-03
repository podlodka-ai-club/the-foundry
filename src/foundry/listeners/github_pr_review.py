from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from .. import shell, triggers
from .base import EmitFn

log = structlog.get_logger(__name__)


class GithubPrReviewListener:
    """Polls GitHub PRs that need the user's attention and emits events.

    Two ``gh search prs`` calls per tick:

    - ``--review-requested=<user>`` → trigger
      :data:`foundry.triggers.GITHUB_PR_REVIEW_REQUESTED`
    - ``--author=<user> --draft=false`` →
      :data:`foundry.triggers.GITHUB_PR_AUTHORED` (optional)

    PRs in both queries collapse into a single ``review_requested`` event.
    Each PR is then enriched with ``headRefOid`` via ``gh pr view`` so that
    ``dedupe_key = "{repo}#{number}@{head_sha}"`` — every push yields a new
    event, and dedup is handled at the DB layer.
    """

    id = "github_pr_review"
    source = "github_pr_review"

    def __init__(
        self,
        *,
        user: str,
        poll_sec: int = 60,
        max_age_days: int = 30,
        skip_repos: tuple[str, ...] = (),
        include_authored: bool = True,
    ) -> None:
        self.user = user
        self.poll_sec = poll_sec
        self.max_age_days = max_age_days
        self.skip_repos = skip_repos
        self.include_authored = include_authored

    def _search_prs(self, *, role: str) -> list[dict[str, Any]]:
        """Run a single ``gh search prs`` call. ``role`` selects the filter."""
        cmd = [
            "gh", "search", "prs",
            "--state", "open",
            "--json", "url,number,repository,author,createdAt,updatedAt",
            "--limit", "100",
        ]
        if role == "review_requested":
            cmd += [f"--review-requested={self.user}"]
        elif role == "authored":
            cmd += [f"--author={self.user}", "--draft=false"]
        else:
            raise ValueError(f"unknown role: {role}")
        result = shell.run(cmd, check=False)
        if not result.ok:
            log.warning(
                "github_pr_review.search_failed",
                role=role,
                stderr=result.stderr[:500],
            )
            return []
        return json.loads(result.stdout or "[]")

    def _fetch_head_sha(self, repo: str, number: int) -> str | None:
        cmd = [
            "gh", "pr", "view", str(number),
            "--repo", repo,
            "--json", "headRefOid",
        ]
        result = shell.run(cmd, check=False)
        if not result.ok:
            log.warning(
                "github_pr_review.pr_view_failed",
                repo=repo,
                number=number,
                stderr=result.stderr[:500],
            )
            return None
        data = json.loads(result.stdout or "{}")
        return data.get("headRefOid") or None

    def _is_skipped(self, repo: str) -> bool:
        return any(p and p in repo for p in self.skip_repos)

    def _is_recent(self, created_at: str) -> bool:
        if not created_at:
            return True
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        cutoff = datetime.now(tz=UTC) - timedelta(days=self.max_age_days)
        return dt >= cutoff

    def _collect_prs(self) -> list[tuple[dict[str, Any], str]]:
        """Return ``(pr, trigger_id)`` pairs after merge + dedup + filtering.

        ``review_requested`` wins over ``authored`` when a PR appears in both.
        """
        seen: dict[str, tuple[dict[str, Any], str]] = {}

        def add(items: list[dict[str, Any]], trigger_id: str) -> None:
            for item in items:
                url = item.get("url") or ""
                if not url or url in seen:
                    continue
                repo = (item.get("repository") or {}).get("nameWithOwner") or ""
                if not repo or self._is_skipped(repo):
                    continue
                if not self._is_recent(item.get("createdAt") or ""):
                    continue
                seen[url] = (item, trigger_id)

        add(
            self._search_prs(role="review_requested"),
            triggers.GITHUB_PR_REVIEW_REQUESTED,
        )
        if self.include_authored:
            add(self._search_prs(role="authored"), triggers.GITHUB_PR_AUTHORED)
        return list(seen.values())

    async def _emit_one(
        self, emit: EmitFn, pr: dict[str, Any], trigger_id: str
    ) -> None:
        repo = (pr.get("repository") or {}).get("nameWithOwner") or ""
        number = int(pr["number"])
        head_sha = await asyncio.to_thread(self._fetch_head_sha, repo, number)
        if not head_sha:
            log.info(
                "github_pr_review.skip_no_sha", repo=repo, number=number
            )
            return
        author = (pr.get("author") or {}).get("login") or ""
        reason = (
            "review_requested"
            if trigger_id == triggers.GITHUB_PR_REVIEW_REQUESTED
            else "authored"
        )
        payload = {
            "repo": repo,
            "number": number,
            "url": pr.get("url") or "",
            "head_sha": head_sha,
            "author": author,
            "reason": reason,
            "created_at": pr.get("createdAt") or "",
            "updated_at": pr.get("updatedAt") or "",
            "short_name": f"PR #{number}",
        }
        await emit(
            trigger_id=trigger_id,
            dedupe_key=f"{repo}#{number}@{head_sha}",
            payload=payload,
        )

    async def tick_once(self, emit: EmitFn) -> None:
        """One poll tick: search → enrich → emit. Public for tests."""
        prs = await asyncio.to_thread(self._collect_prs)
        for pr, trigger_id in prs:
            await self._emit_one(emit, pr, trigger_id)

    async def listen(self, emit: EmitFn) -> None:
        while True:
            try:
                await self.tick_once(emit)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("listener.tick.error", listener=self.id)
            await asyncio.sleep(self.poll_sec)
