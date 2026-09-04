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


def _format_error(error: Any) -> str:
    location = ".".join(str(part) for part in error.absolute_path) or "<root>"
    return f"{location}: {error.message}"
