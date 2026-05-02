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
    matched = automations_for_trigger("github_issues")
    empty = automations_for_trigger("nope")

    # Assert
    assert [a.id for a in matched] == ["dev_task"]
    assert empty == []


def test_automation_is_frozen() -> None:
    # Arrange
    automation = AUTOMATIONS[0]
    assert isinstance(automation, Automation)

    # Act / Assert
    with pytest.raises(FrozenInstanceError):
        automation.id = "mutated"  # type: ignore[misc]
