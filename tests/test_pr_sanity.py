from __future__ import annotations

import pytest

from foundry.stages.pr import MAX_FILES_PER_PR, _sanity_check_changes


def test_sanity_check_accepts_small_clean_change() -> None:
    lines = [" M src/foundry/pipeline.py", "?? README.md"]

    _sanity_check_changes(lines)


def test_sanity_check_rejects_too_many_files() -> None:
    lines = [f" M file_{i}.py" for i in range(MAX_FILES_PER_PR + 1)]

    with pytest.raises(RuntimeError, match="sandbox escape"):
        _sanity_check_changes(lines)


def test_sanity_check_rejects_pycache_paths() -> None:
    lines = [" M src/foundry/__pycache__/pipeline.cpython-311.pyc"]

    with pytest.raises(RuntimeError, match="forbidden paths"):
        _sanity_check_changes(lines)


def test_sanity_check_rejects_venv_paths() -> None:
    lines = [" M .venv/bin/activate"]

    with pytest.raises(RuntimeError, match="forbidden paths"):
        _sanity_check_changes(lines)


def test_sanity_check_rejects_ds_store() -> None:
    lines = ["?? .DS_Store"]

    with pytest.raises(RuntimeError, match="forbidden paths"):
        _sanity_check_changes(lines)


def test_sanity_check_allows_env_example() -> None:
    """`.env.example` must not be caught by a forbidden substring — it's legitimate."""
    lines = [" M .env.example"]

    _sanity_check_changes(lines)
