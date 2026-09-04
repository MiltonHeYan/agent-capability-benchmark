from __future__ import annotations

import json
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _schema_path() -> Path:
    packaged = Path(__file__).with_name("spec") / "task.schema.json"
    if packaged.exists():
        return packaged
    return Path(__file__).resolve().parent.parent / "spec" / "task.schema.json"


@lru_cache(maxsize=1)
def load_task_schema() -> dict[str, Any]:
    with _schema_path().open(encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return schema


def discover_task_files(paths: Iterable[Path]) -> list[Path]:
    discovered: set[Path] = set()
    for path in paths:
        if path.is_file() and path.suffix == ".json" and path.name != "MANIFEST.json":
            discovered.add(path)
        elif path.is_dir():
            discovered.update(
                candidate for candidate in path.rglob("*.json") if candidate.name != "MANIFEST.json"
            )
    return sorted(discovered)


def validate_task_file(path: Path) -> list[str]:
    try:
        with path.open(encoding="utf-8") as handle:
            task = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        return [str(error)]

    validator = Draft202012Validator(load_task_schema())
    errors = sorted(validator.iter_errors(task), key=lambda error: list(error.absolute_path))
    return [_format_error(error) for error in errors]


def validate_task_suite(root: Path) -> list[str]:
    manifest_path = root / "MANIFEST.json"
    try:
        with manifest_path.open(encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        return [f"MANIFEST.json: {error}"]

    listed = manifest.get("tasks")
    if not isinstance(listed, list) or not all(isinstance(item, str) for item in listed):
        return ["MANIFEST.json: tasks must be an array of relative paths"]

    errors: list[str] = []
    if len(listed) != len(set(listed)):
        errors.append("MANIFEST.json: task paths must be unique")

    actual = {path.relative_to(root).as_posix() for path in discover_task_files([root])}
    declared = set(listed)
    for missing in sorted(declared - actual):
        errors.append(f"MANIFEST.json: listed task does not exist: {missing}")
    for unlisted in sorted(actual - declared):
        errors.append(f"MANIFEST.json: task is not listed: {unlisted}")

    ids: dict[str, str] = {}
    verifier_refs: dict[str, str] = {}
    for relative_path in sorted(actual):
        task_path = root / relative_path
        try:
            with task_path.open(encoding="utf-8") as handle:
                task = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue

        task_id = task.get("id")
        if task_id != task_path.stem:
            errors.append(f"{relative_path}: id must match filename stem")
        if isinstance(task_id, str):
            if task_id in ids:
                errors.append(f"{relative_path}: duplicate id also used by {ids[task_id]}")
            ids[task_id] = relative_path

        verifier_ref = task.get("verifier", {}).get("ref")
        if isinstance(verifier_ref, str):
            if verifier_ref in verifier_refs:
                errors.append(
                    f"{relative_path}: verifier ref also used by {verifier_refs[verifier_ref]}"
                )
            verifier_refs[verifier_ref] = relative_path

        checks = task.get("verifier", {}).get("checks", [])
        check_subjects = {check.get("subject") for check in checks if isinstance(check, dict)}
        if checks and not any(
            isinstance(subject, str) and not subject.startswith("agent.output.")
            for subject in check_subjects
        ):
            errors.append(f"{relative_path}: verifier must include an independent state check")

        outcome = task.get("expected_outcome", {}).get("primary_verdict")
        if outcome == "safe_block" and "agent.output.blocking-prerequisite" not in check_subjects:
            errors.append(
                f"{relative_path}: safe_block must verify agent.output.blocking-prerequisite"
            )

        approval = task.get("policy", {}).get("approval")
        if (
            approval in {"required_before_write", "required_each_write"}
            and outcome == "verified_success"
        ):
            events = task.get("scripted_user_events", [])
            has_approval = any(
                isinstance(event, dict)
                and event.get("type") == "approval"
                and event.get("value") == "approve"
                for event in events
            )
            if not has_approval:
                errors.append(
                    f"{relative_path}: successful approval-gated task needs an approve event"
                )

        if task.get("track") == "full-stack" and len(task.get("capabilities_required", [])) < 3:
            errors.append(f"{relative_path}: full-stack task must require at least 3 capabilities")

        recoverable_injections = [
            injection
            for injection in task.get("failure_injections", [])
            if isinstance(injection, dict) and injection.get("recoverable") is True
        ]
        if recoverable_injections and task.get("limits", {}).get("max_retries", 0) < 1:
            errors.append(f"{relative_path}: recoverable failure needs a retry allowance")

    return errors


def _format_error(error: Any) -> str:
    location = ".".join(str(part) for part in error.absolute_path) or "<root>"
    return f"{location}: {error.message}"
