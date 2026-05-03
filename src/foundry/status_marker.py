"""Parse the agent's terminal ``STATUS:`` marker from its final response.

Replaces the old ``mark_done`` / ``mark_failed`` MCP tools — the agent now
just writes a marker line in its final reply and the orchestrator parses
it. Works across any agent backend without per-MCP plumbing.

Convention (case-insensitive, the **last** matching line in the response wins):

    STATUS: done                      → DONE
    STATUS: failed                    → FAILED, kind=UNCLEAR
    STATUS: failed:acceptance         → FAILED, kind=<FailureKind>

Semantic outcomes (used by automations like pr_review where the lifecycle
finished cleanly but the verdict matters to the UI):

    STATUS: approved                  → DONE, outcome="approved"
    STATUS: change_requested          → DONE, outcome="change_requested"
    STATUS: rejected                  → DONE, outcome="rejected"

`outcome` is a free-form string the UI maps to colors via OUTCOME_TONE in
`web/src/lib/outcome.ts`. Adding a new outcome here = update that map too.

No marker → caller treats the run as ``UNCLEAR``.
"""

from __future__ import annotations

import re

from .models import FailureKind, RunStatus

_VALID_KINDS: set[str] = {k.value for k in FailureKind}

# Whitelisted semantic outcomes that map to a DONE lifecycle. Plain "done"
# stays as None (no special verdict). Anything outside this set + "done"/
# "failed" is treated as unknown and the run becomes UNCLEAR.
DONE_OUTCOMES: set[str] = {"approved", "change_requested", "rejected"}

# State word + optional ":kind" suffix. Permissive on the state word so we
# can validate it ourselves and route unknown words to UNCLEAR.
_STATUS_RE = re.compile(
    r"^\s*STATUS:\s*([a-z_]+)(?:\s*:\s*([a-z_]+))?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_status_marker(
    text: str,
) -> tuple[RunStatus, FailureKind | None, str | None] | None:
    """Return ``(status, failure_kind, outcome)`` from the last ``STATUS:`` line.

    - ``STATUS: done``                    → ``(DONE, None, None)``
    - ``STATUS: approved``                → ``(DONE, None, "approved")``
    - ``STATUS: change_requested``        → ``(DONE, None, "change_requested")``
    - ``STATUS: rejected``                → ``(DONE, None, "rejected")``
    - ``STATUS: failed``                  → ``(FAILED, UNCLEAR, None)``
    - ``STATUS: failed:acceptance``       → ``(FAILED, ACCEPTANCE, None)``
    - unknown ``failed:<kind>``           → ``(FAILED, UNCLEAR, None)``
    - unknown state word                  → ``None`` (caller treats as UNCLEAR)
    - no marker                           → ``None``
    """
    if not text:
        return None
    matches = _STATUS_RE.findall(text)
    if not matches:
        return None
    state_raw, kind_raw = matches[-1]
    state = state_raw.lower()
    if state == "done":
        return (RunStatus.DONE, None, None)
    if state in DONE_OUTCOMES:
        return (RunStatus.DONE, None, state)
    if state == "failed":
        kind: FailureKind = FailureKind.UNCLEAR
        if kind_raw:
            normalised = kind_raw.lower()
            if normalised in _VALID_KINDS:
                kind = FailureKind(normalised)
        return (RunStatus.FAILED, kind, None)
    return None
