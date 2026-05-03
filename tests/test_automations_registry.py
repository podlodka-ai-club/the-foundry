from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from foundry.automations import (
    AUTOMATIONS,
    Automation,
    automations_for_trigger,
    get_automation,
)


def test_automations_list_not_empty() -> None:
    assert len(AUTOMATIONS) >= 1


def test_automation_ids_unique() -> None:
    # Arrange / Act
    ids = [a.id for a in AUTOMATIONS]

    # Assert
    assert len(ids) == len(set(ids))


def test_get_automation_by_id() -> None:
    # Act
    found = get_automation("dev_task")
    missing = get_automation("nope")

    # Assert
    assert found is not None
    assert found.id == "dev_task"
    assert missing is None


def test_automations_for_trigger_filters() -> None:
    # Act
    matched = automations_for_trigger("github_issues.issue_opened")
    empty = automations_for_trigger("nope")

    # Assert
    assert "dev_task" in [a.id for a in matched]
    assert "tg_chat" not in [a.id for a in matched]
    assert empty == []


def test_dev_task_uses_git_worktree() -> None:
    auto = get_automation("dev_task")
    assert auto is not None

    assert auto.workspace == "git_worktree"
    assert auto.cwd is None


def test_tg_chat_uses_fixed_cwd() -> None:
    auto = get_automation("tg_chat")
    assert auto is not None

    # tg_chat needs a stable cwd — Claude CLI's --resume is indexed by
    # cwd hash, so a moving worktree would break multi-turn chat.
    assert auto.workspace == "fixed"
    assert auto.cwd is not None


def test_pr_review_uses_pr_worktree_and_session_key() -> None:
    auto = get_automation("pr_review")
    assert auto is not None

    assert auto.workspace == "pr_worktree"
    assert auto.session_key is not None
    assert "github_pr_review.review_requested" in auto.triggers
    assert "github_pr_review.authored" in auto.triggers


def test_pr_review_subscribes_to_review_requested() -> None:
    matched = automations_for_trigger("github_pr_review.review_requested")

    assert "pr_review" in [a.id for a in matched]
    assert "dev_task" not in [a.id for a in matched]


def test_automation_is_frozen() -> None:
    # Arrange
    automation = AUTOMATIONS[0]
    assert isinstance(automation, Automation)

    # Act / Assert
    with pytest.raises(FrozenInstanceError):
        automation.id = "mutated"  # type: ignore[misc]


def test_automation_fixed_workspace_requires_cwd() -> None:
    with pytest.raises(ValueError, match="workspace='fixed' requires cwd"):
        Automation(
            id="bad",
            name="bad",
            description="t",
            triggers=("github_issues.issue_opened",),
            agent={"backend": "stub", "model": None},
            prompt_path="",
            workspace="fixed",
        )
