from __future__ import annotations

import string

from foundry.session import compute_session_id


def test_compute_session_id_deterministic() -> None:
    # Arrange
    args = ("issue-1", "dev_task", "claude_cli")

    # Act
    a = compute_session_id(*args)
    b = compute_session_id(*args)

    # Assert
    assert a == b
    assert len(a) == 16
    assert all(ch in string.hexdigits for ch in a)


def test_compute_session_id_differs_per_external_id() -> None:
    # Act
    a = compute_session_id("issue-1", "dev_task", "claude_cli")
    b = compute_session_id("issue-2", "dev_task", "claude_cli")

    # Assert
    assert a != b


def test_compute_session_id_differs_per_automation_id() -> None:
    # Act
    a = compute_session_id("issue-1", "dev_task", "claude_cli")
    b = compute_session_id("issue-1", "triage", "claude_cli")

    # Assert
    assert a != b


def test_compute_session_id_differs_per_agent_type() -> None:
    # Act
    a = compute_session_id("issue-1", "dev_task", "claude_cli")
    b = compute_session_id("issue-1", "dev_task", "codex_cli")

    # Assert
    assert a != b


def test_compute_session_id_known_value() -> None:
    # Act
    sid = compute_session_id("issue-1", "dev_task", "claude_cli")

    # Assert — locked-in value; changing the algorithm requires deliberate update.
    assert sid == "bcdb3472f41d8be3"


def test_compute_session_id_handles_unicode() -> None:
    # Arrange
    args = ("issue#1 ★", "dev_task", "claude_cli")

    # Act
    a = compute_session_id(*args)
    b = compute_session_id(*args)

    # Assert
    assert a == b
    assert len(a) == 16
