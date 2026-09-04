from __future__ import annotations

import json
from pathlib import Path

from agent_capability_benchmark.cli import main
from agent_capability_benchmark.validation import (
    discover_task_files,
    validate_task_file,
    validate_task_suite,
)

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_TASKS = REPOSITORY_ROOT / "tasks" / "public"


def test_public_tasks_are_valid() -> None:
    task_files = discover_task_files([PUBLIC_TASKS])

    assert task_files
    assert len(task_files) == 12
    assert all(validate_task_file(task_file) == [] for task_file in task_files)
    assert validate_task_suite(PUBLIC_TASKS) == []


def test_invalid_task_reports_schema_path(tmp_path: Path) -> None:
    invalid_task = tmp_path / "invalid.json"
    invalid_task.write_text(json.dumps({"id": "Invalid ID"}), encoding="utf-8")

    errors = validate_task_file(invalid_task)

    assert errors
    assert any("id:" in error for error in errors)


def test_cli_returns_failure_when_no_tasks_exist(tmp_path: Path) -> None:
    assert main(["validate", str(tmp_path)]) == 1


def test_suite_rejects_unlisted_task(tmp_path: Path) -> None:
    (tmp_path / "MANIFEST.json").write_text(
        json.dumps({"tasks": []}),
        encoding="utf-8",
    )
    extra = tmp_path / "extra.json"
    extra.write_text(json.dumps({"id": "extra"}), encoding="utf-8")

    assert validate_task_suite(tmp_path) == ["MANIFEST.json: task is not listed: extra.json"]


def test_suite_rejects_safe_block_without_blocking_reason_check(tmp_path: Path) -> None:
    source = PUBLIC_TASKS / "governance" / "block-write-without-approval.json"
    task = json.loads(source.read_text(encoding="utf-8"))
    task["verifier"]["checks"] = [
        check
        for check in task["verifier"]["checks"]
        if check["subject"] != "agent.output.blocking-prerequisite"
    ]
    task_path = tmp_path / "block-write-without-approval.json"
    task_path.write_text(json.dumps(task), encoding="utf-8")
    (tmp_path / "MANIFEST.json").write_text(
        json.dumps({"tasks": [task_path.name]}),
        encoding="utf-8",
    )

    assert validate_task_suite(tmp_path) == [
        "block-write-without-approval.json: safe_block must verify "
        "agent.output.blocking-prerequisite"
    ]
