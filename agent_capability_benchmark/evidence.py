from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _schema_path() -> Path:
    packaged = Path(__file__).with_name("spec") / "evidence.schema.json"
    if packaged.exists():
        return packaged
    return Path(__file__).resolve().parent.parent / "spec" / "evidence.schema.json"


@lru_cache(maxsize=1)
def load_evidence_schema() -> dict[str, Any]:
    with _schema_path().open(encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return schema


def load_evidence(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        evidence = json.load(handle)
    errors = validate_evidence(evidence)
    if errors:
        joined = "\n".join(f"- {error}" for error in errors)
        raise ValueError(f"invalid evidence file {path}:\n{joined}")
    return evidence


def validate_evidence(evidence: Any) -> list[str]:
    validator = Draft202012Validator(load_evidence_schema())
    errors = sorted(
        validator.iter_errors(evidence),
        key=lambda error: list(error.absolute_path),
    )
    return [_format_error(error) for error in errors]


def _format_error(error: Any) -> str:
    location = ".".join(str(part) for part in error.absolute_path) or "<root>"
    return f"{location}: {error.message}"
