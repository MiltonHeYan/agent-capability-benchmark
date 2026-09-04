from __future__ import annotations

import pytest

from agent_capability_benchmark.evidence import validate_evidence
from agent_capability_benchmark.verifier import verify_task_evidence


def _task(checks: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": "verifier-contract",
        "verifier": {
            "checks": checks,
        },
    }


def _evidence() -> dict[str, object]:
    return {
        "task_id": "verifier-contract",
        "run_id": "run-1",
        "observations": {
            "agent": {"output": {"message": "Blocked by approval"}},
            "fixture": {"records": [{"id": "record-1"}], "mutation-count": 1},
            "ledger": {"total-cost-usd": 0.05},
            "source": {"record": {"id": "source-1", "body": "unchanged"}},
        },
        "baseline": {
            "source": {"record": {"id": "source-1", "body": "unchanged"}},
        },
        "references": {
            "fixture://expected/record": {"id": "record-1"},
        },
        "events": [],
        "metadata": {},
    }


def test_verifier_supports_all_public_operators() -> None:
    task = _task(
        [
            {
                "subject": "fixture.records.0",
                "operator": "equals",
                "expected_ref": "fixture://expected/record",
            },
            {
                "subject": "agent.output.message",
                "operator": "contains",
                "expected": "approval",
            },
            {
                "subject": "fixture.records",
                "operator": "count-equals",
                "expected": 1,
            },
            {"subject": "fixture.records", "operator": "exists"},
            {"subject": "fixture.deleted", "operator": "not-exists"},
            {"subject": "source.record", "operator": "unchanged"},
            {
                "subject": "ledger.total-cost-usd",
                "operator": "less-than-or-equal",
                "expected": 0.1,
            },
        ]
    )
    evidence = _evidence()

    result = verify_task_evidence(task, evidence)

    assert result.passed
    assert result.passed_checks == 7


def test_verifier_rejects_task_mismatch() -> None:
    evidence = _evidence()
    evidence["task_id"] = "different-task"

    with pytest.raises(ValueError, match="does not match"):
        verify_task_evidence(_task([]), evidence)


def test_evidence_schema_rejects_missing_run_id() -> None:
    evidence = _evidence()
    del evidence["run_id"]

    errors = validate_evidence(evidence)

    assert errors
    assert any("run_id" in error for error in errors)
