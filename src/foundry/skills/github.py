"""GitHub-side skills (issue reactions for now)."""

from __future__ import annotations

import os
from typing import Any

from foundry import shell

# Map of conventional emojis to GitHub reaction `content` values.
# https://docs.github.com/en/rest/reactions/reactions
_EMOJI_TO_CONTENT: dict[str, str] = {
    "+1": "+1",
    "👍": "+1",
    "thumbs_up": "+1",
    "-1": "-1",
    "👎": "-1",
    "thumbs_down": "-1",
    "laugh": "laugh",
    "😄": "laugh",
    "hooray": "hooray",
    "🎉": "hooray",
    "confused": "confused",
    "😕": "confused",
    "heart": "heart",
    "❤️": "heart",
    "rocket": "rocket",
    "🚀": "rocket",
    "eyes": "eyes",
    "👀": "eyes",
}


def react_emoji_impl(*, emoji: str) -> dict[str, Any]:
    """React on the source issue with one of GitHub's eight allowed emojis."""
    content = _EMOJI_TO_CONTENT.get(emoji)
    if content is None:
        return {"ok": False, "error": "unknown emoji"}

    source_repo = os.environ.get("FOUNDRY_SOURCE_REPO")
    issue_number = os.environ.get("FOUNDRY_ISSUE_NUMBER")
    if not source_repo or not issue_number:
        return {"ok": False, "error": "missing source_repo or issue_number"}

    shell.run(
        [
            "gh", "api",
            f"repos/{source_repo}/issues/{issue_number}/reactions",
            "-f", f"content={content}",
            "-X", "POST",
        ],
        check=False,
    )
    return {"ok": True}


__all__ = ["react_emoji_impl"]
