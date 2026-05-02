from __future__ import annotations

from pathlib import Path

from foundry.agents import AgentSettings, AgentStage, AgentTask
from foundry.agents.context import agent_event_context
from foundry.agents.stub import StubAgent
from foundry.events import read_events
from foundry.state import init_db


def _task() -> AgentTask:
    return AgentTask(id=7, title="do the thing", description="please")


def test_stub_plan_returns_trivial_plan_text() -> None:
    agent = StubAgent(settings=AgentSettings(stage=AgentStage.PLAN))

    result = agent.apply(task=_task(), worktree=Path("/tmp"), input="")

    assert result.stage is AgentStage.PLAN
    assert "stub plan for issue #7" in result.response
    assert "do the thing" in result.response
    assert result.result == "stub plan for issue #7"


def test_stub_verify_always_passes() -> None:
    agent = StubAgent(settings=AgentSettings(stage=AgentStage.VERIFY))

    result = agent.apply(task=_task(), worktree=Path("/tmp"), input="some diff")

    assert result.stage is AgentStage.VERIFY
    assert result.result == "PASS"


def test_stub_implement_appends_line_to_existing_readme(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("existing\n")
    agent = StubAgent(settings=AgentSettings(stage=AgentStage.IMPLEMENT))

    agent.apply(task=_task(), worktree=tmp_path, input="")

    content = (tmp_path / "README.md").read_text()
    assert content == "existing\nfoundry-bot: task #7 — do the thing\n"


def test_stub_implement_adds_leading_newline_when_file_has_no_trailing_newline(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_bytes(b"no newline at end")
    agent = StubAgent(settings=AgentSettings(stage=AgentStage.IMPLEMENT))

    agent.apply(task=_task(), worktree=tmp_path, input="")

    content = (tmp_path / "README.md").read_text()
    assert content == "no newline at end\nfoundry-bot: task #7 — do the thing\n"


def test_stub_implement_creates_readme_when_missing(tmp_path: Path) -> None:
    agent = StubAgent(settings=AgentSettings(stage=AgentStage.IMPLEMENT))

    agent.apply(task=_task(), worktree=tmp_path, input="")

    content = (tmp_path / "README.md").read_text()
    assert content == "foundry-bot: task #7 — do the thing\n"


def test_stub_get_session_id_is_always_none() -> None:
    agent = StubAgent(settings=AgentSettings(stage=AgentStage.IMPLEMENT))

    assert agent.get_session_id(_task()) is None


def test_record_uses_parent_event_seq_from_context(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    agent = StubAgent(
        settings=AgentSettings(stage=AgentStage.IMPLEMENT, db_path=db)
    )

    with agent_event_context(parent_event_seq=42):
        agent.apply(task=_task(), worktree=tmp_path, input="")

    events = read_events(db, run_id=7)
    assert events, "expected events to be persisted"
    for ev in events:
        assert ev.parent_event_seq == 42, (
            f"event {ev.kind} seq={ev.seq} has parent_event_seq={ev.parent_event_seq}"
        )
