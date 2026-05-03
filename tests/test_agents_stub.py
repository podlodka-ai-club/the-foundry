from __future__ import annotations

from pathlib import Path

from foundry.agents import AgentSettings, AgentTask
from foundry.agents.context import agent_event_context
from foundry.agents.stub import StubAgent
from foundry.events import read_events
from foundry.state import init_db


def _task() -> AgentTask:
    return AgentTask(id=7, title="do the thing", description="please")


def test_stub_appends_line_to_existing_readme(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("existing\n")
    agent = StubAgent(settings=AgentSettings())

    agent.apply(task=_task(), worktree=tmp_path, input="")

    content = (tmp_path / "README.md").read_text()
    assert content == "existing\nfoundry-bot: task #7 — do the thing\n"


def test_stub_adds_leading_newline_when_file_has_no_trailing_newline(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_bytes(b"no newline at end")
    agent = StubAgent(settings=AgentSettings())

    agent.apply(task=_task(), worktree=tmp_path, input="")

    content = (tmp_path / "README.md").read_text()
    assert content == "no newline at end\nfoundry-bot: task #7 — do the thing\n"


def test_stub_creates_readme_when_missing(tmp_path: Path) -> None:
    agent = StubAgent(settings=AgentSettings())

    agent.apply(task=_task(), worktree=tmp_path, input="")

    content = (tmp_path / "README.md").read_text()
    assert content == "foundry-bot: task #7 — do the thing\n"


def test_stub_returns_summary(tmp_path: Path) -> None:
    agent = StubAgent(settings=AgentSettings())

    result = agent.apply(task=_task(), worktree=tmp_path, input="")

    assert result.result.startswith("appended 1 line to README.md")
    assert result.response == result.result


def test_stub_get_session_id_is_always_none() -> None:
    agent = StubAgent(settings=AgentSettings())

    assert agent.get_session_id(_task()) is None


def test_record_uses_parent_event_seq_from_context(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    agent = StubAgent(settings=AgentSettings(db_path=db))

    with agent_event_context(parent_event_seq=42):
        agent.apply(task=_task(), worktree=tmp_path, input="")

    events = read_events(db, run_id=7)
    assert events, "expected events to be persisted"
    for ev in events:
        assert ev.parent_event_seq == 42, (
            f"event {ev.kind} seq={ev.seq} has parent_event_seq={ev.parent_event_seq}"
        )
