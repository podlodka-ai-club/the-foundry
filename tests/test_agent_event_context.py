from __future__ import annotations

from foundry.agents.context import agent_event_context, get_parent_event_seq


def test_default_is_none() -> None:
    assert get_parent_event_seq() is None


def test_setter_restores_on_exit() -> None:
    assert get_parent_event_seq() is None

    with agent_event_context(parent_event_seq=5):
        assert get_parent_event_seq() == 5
        with agent_event_context(parent_event_seq=10):
            assert get_parent_event_seq() == 10
        assert get_parent_event_seq() == 5

    assert get_parent_event_seq() is None


def test_set_to_none_inside_outer_context() -> None:
    with agent_event_context(parent_event_seq=7):
        with agent_event_context(parent_event_seq=None):
            assert get_parent_event_seq() is None
        assert get_parent_event_seq() == 7
