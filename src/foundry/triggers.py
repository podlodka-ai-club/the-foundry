"""Canonical trigger ids — single source of truth.

Naming: ``<namespace>.<event>`` (dots, not colons). Cron rules live in their
own ``cron.<rule_id>`` namespace and are registered separately from the
static set below (rules are user-configurable).

Used by:
- Listeners — emit one of these as ``trigger_id`` via ``dispatch_event``.
- Automations — declare ``triggers=(<TRIGGER_ID>, ...)`` in the registry.
- API ``/api/triggers`` — enumerate the known set for the UI footer.
- Startup validation (``validate_registry``) — reject automations referencing
  unknown trigger ids before the daemon starts.
"""

from __future__ import annotations

GITHUB_ISSUE_OPENED = "github_issues.issue_opened"
GITHUB_PR_REVIEW_REQUESTED = "github_pr_review.review_requested"
GITHUB_PR_AUTHORED = "github_pr_review.authored"
TELEGRAM_MESSAGE = "telegram.message"
DISCORD_MESSAGE = "discord.message"

# Static set — cron triggers are added dynamically from CronRule.id.
ALL: frozenset[str] = frozenset(
    {
        GITHUB_ISSUE_OPENED,
        GITHUB_PR_REVIEW_REQUESTED,
        GITHUB_PR_AUTHORED,
        TELEGRAM_MESSAGE,
        DISCORD_MESSAGE,
    }
)

CRON_NAMESPACE = "cron."


def is_known(trigger_id: str) -> bool:
    """True if ``trigger_id`` is in the static set or namespaced as cron."""
    return trigger_id in ALL or trigger_id.startswith(CRON_NAMESPACE)


def validate_registry(automations: list, known_cron_rule_ids: tuple[str, ...] = ()) -> None:
    """Raise ``ValueError`` if any automation references an unknown trigger.

    Cron triggers are valid iff they reference a rule id in
    ``known_cron_rule_ids`` (so typos in cron rule names are caught too).
    """
    cron_known = {f"{CRON_NAMESPACE}{rid}" for rid in known_cron_rule_ids}
    for a in automations:
        for t in a.triggers:
            if t in ALL:
                continue
            if t.startswith(CRON_NAMESPACE):
                if t in cron_known:
                    continue
                raise ValueError(
                    f"automation {a.id!r} references unknown cron trigger {t!r}"
                )
            raise ValueError(
                f"automation {a.id!r} references unknown trigger {t!r}"
            )
