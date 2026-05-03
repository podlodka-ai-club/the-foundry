from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from foundry import state
from foundry.events import read_events, record_event, stage_span


def test_record_event_returns_monotonic_seq(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    state.init_db(db)

    # Act
    s1 = record_event(db, task_id=1, stage="plan", kind="stage_started", payload={})
    s2 = record_event(db, task_id=1, stage="plan", kind="agent_text", payload={"text": "hi"})
    s3 = record_event(db, task_id=1, stage="plan", kind="stage_finished", payload={})

    # Assert
    assert (s1, s2, s3) == (1, 2, 3)


def test_record_event_atomic_under_threads(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    n = 20

    # Act
    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = [
            pool.submit(
                record_event,
                db,
                1,
                "implement",
                "agent_tool",
                {"tool": f"t{i}"},
            )
            for i in range(n)
        ]
        seqs = sorted(f.result() for f in as_completed(futures))

    # Assert
    assert seqs == list(range(1, n + 1))

    events = read_events(db, task_id=1)
    assert [e.seq for e in events] == list(range(1, n + 1))
    assert len({e.seq for e in events}) == n


def test_read_events_with_after_seq_returns_tail(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    for i in range(5):
        record_event(db, task_id=1, stage="plan", kind="agent_text", payload={"text": f"m{i}"})

    # Act
    tail = read_events(db, task_id=1, after_seq=3)

    # Assert
    assert [e.seq for e in tail] == [4, 5]
    assert tail[0].payload == {"text": "m3"}
    assert tail[1].payload == {"text": "m4"}


def test_truncation_long_text(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    long_text = "a" * (100 * 1024)  # 100KB

    # Act
    record_event(db, task_id=1, stage="plan", kind="agent_text", payload={"text": long_text})
    events = read_events(db, task_id=1)

    # Assert
    assert len(events) == 1
    field = events[0].payload["text"]
    assert isinstance(field, dict)
    assert field["truncated"] is True
    assert field["original_size"] == 100 * 1024
    assert len(field["text"].encode("utf-8")) <= 64 * 1024


def test_truncation_short_critical_fields_untouched(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    payload = {
        "summary": "s" * 100,
        "error": "e" * 100,
        "tool": "t" * 100,
        "detail": "d" * 100,
        "model": "m" * 100,
    }

    # Act
    record_event(db, task_id=1, stage="plan", kind="agent_result", payload=payload)
    events = read_events(db, task_id=1)

    # Assert
    assert events[0].payload == payload


def test_stage_span_emits_started_and_finished_without_finish_call(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    state.init_db(db)

    # Act
    with stage_span(db, task_id=1, stage="plan"):
        pass

    # Assert
    events = read_events(db, task_id=1)
    kinds = [e.kind for e in events]
    assert kinds == ["stage_started", "stage_finished"]
    assert "duration_ms" in events[1].payload
    assert "output" not in events[1].payload


def test_stage_span_emits_finished_with_output_from_finish(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    state.init_db(db)

    # Act
    with stage_span(db, task_id=1, stage="plan") as finish:
        finish(output={"k": "v"}, cost_usd=0.01, tokens_in=10, tokens_out=20)

    # Assert
    events = read_events(db, task_id=1)
    assert [e.kind for e in events] == ["stage_started", "stage_finished"]
    finished = events[1].payload
    assert finished["output"] == {"k": "v"}
    assert finished["cost_usd"] == 0.01
    assert finished["tokens_in"] == 10
    assert finished["tokens_out"] == 20
    assert "duration_ms" in finished


def test_stage_span_emits_failed_on_exception(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    state.init_db(db)

    # Act
    with pytest.raises(RuntimeError, match="boom"):
        with stage_span(db, task_id=1, stage="implement"):
            raise RuntimeError("boom")

    # Assert
    events = read_events(db, task_id=1)
    kinds = [e.kind for e in events]
    assert kinds == ["stage_started", "stage_failed"]
    failed = events[1].payload
    assert "duration_ms" in failed
    assert "boom" in failed["error"]
    assert "RuntimeError" in failed["traceback"]


def test_stage_span_started_includes_input_and_agent_when_provided(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    state.init_db(db)

    # Act
    with stage_span(
        db,
        task_id=1,
        stage="plan",
        input={"title": "t"},
        agent={"name": "stub", "model": "haiku"},
    ):
        pass

    # Assert
    events = read_events(db, task_id=1)
    started = events[0].payload
    assert started["input"] == {"title": "t"}
    assert started["agent"] == {"name": "stub", "model": "haiku"}


def test_different_tasks_have_independent_seq(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    state.init_db(db)

    # Act
    s1_first = record_event(db, task_id=1, stage="plan", kind="stage_started", payload={})
    s2_first = record_event(db, task_id=2, stage="plan", kind="stage_started", payload={})
    s1_second = record_event(db, task_id=1, stage="plan", kind="stage_finished", payload={})
    s2_second = record_event(db, task_id=2, stage="plan", kind="stage_finished", payload={})

    # Assert
    assert s1_first == 1
    assert s2_first == 1
    assert s1_second == 2
    assert s2_second == 2
