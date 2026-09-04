from __future__ import annotations

import json
from pathlib import Path

from agent_capability_benchmark.cli import main
from agent_capability_benchmark.validation import (
    discover_task_files,
    validate_task_file,
)

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_TASKS = REPOSITORY_ROOT / "tasks" / "public"


def test_public_tasks_are_valid() -> None:
    task_files = discover_task_files([PUBLIC_TASKS])

    assert task_files
    assert all(validate_task_file(task_file) == [] for task_file in task_files)


def test_invalid_task_reports_schema_path(tmp_path: Path) -> None:
    invalid_task = tmp_path / "invalid.json"
    invalid_task.write_text(json.dumps({"id": "Invalid ID"}), encoding="utf-8")

    errors = validate_task_file(invalid_task)

    assert errors
    assert any("id:" in error for error in errors)


def test_cli_returns_failure_when_no_tasks_exist(tmp_path: Path) -> None:
    assert main(["validate", str(tmp_path)]) == 1
