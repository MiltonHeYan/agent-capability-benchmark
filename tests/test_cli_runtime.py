from __future__ import annotations

import json
from pathlib import Path

from agent_capability_benchmark.cli import main

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
TASK = REPOSITORY_ROOT / "tasks" / "public" / "core" / "read-known-record.json"


def _write_evidence(path: Path, *, mutation_count: int) -> None:
    path.write_text(
        json.dumps(
            {
                "task_id": "read-known-record",
                "run_id": "reference-run-1",
                "observations": {
                    "agent": {
                        "output": {
                            "record-title": "Quarterly planning note",
                            "record-body": "Freeze the release candidate on Friday.",
                        }
                    },
                    "fixture": {"mutation-count": mutation_count},
                },
                "baseline": {"fixture": {"mutation-count": 0}},
                "references": {
                    "fixture://core/read-known-record/title": "Quarterly planning note",
                    "fixture://core/read-known-record/body": "Freeze the release candidate on Friday.",
                },
                "events": [],
                "metadata": {"fixture_runtime": "reference"},
            }
        ),
        encoding="utf-8",
    )


def test_verify_command_accepts_matching_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    _write_evidence(evidence, mutation_count=0)

    assert main(["verify", str(TASK), str(evidence)]) == 0


def test_verify_command_rejects_failed_check(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    _write_evidence(evidence, mutation_count=1)

    assert main(["verify", str(TASK), str(evidence)]) == 1
