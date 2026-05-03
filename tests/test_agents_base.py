from __future__ import annotations

from foundry.agents import first_line


def test_first_line_returns_first_non_empty_line() -> None:
    result = first_line("\n\n  hello world  \nsecond\n")

    assert result == "hello world"


def test_first_line_truncates_to_limit() -> None:
    result = first_line("a" * 500, limit=10)

    assert result == "a" * 10


def test_first_line_on_empty_input_returns_empty_string() -> None:
    assert first_line("") == ""
    assert first_line("\n   \n") == ""
