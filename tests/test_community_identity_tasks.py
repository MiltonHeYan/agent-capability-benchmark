from __future__ import annotations

import json
from pathlib import Path

from agent_capability_benchmark.verifier import verify_task_evidence

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_TASKS = REPOSITORY_ROOT / "tasks" / "public"


def _load_task(relative_path: str) -> dict[str, object]:
    return json.loads((PUBLIC_TASKS / relative_path).read_text(encoding="utf-8"))


def _evidence(
    task_id: str,
    observations: dict[str, object],
    references: dict[str, object],
) -> dict[str, object]:
    return {
        "task_id": task_id,
        "run_id": "run-community-feedback",
        "observations": observations,
        "baseline": {},
        "references": references,
        "events": [],
        "metadata": {},
    }


def test_credential_recovery_requires_stable_principal_and_target_state() -> None:
    task = _load_task("authentication/preserve-principal-after-credential-recovery.json")
    references = {
        "fixture://authentication/preserve-principal-after-credential-recovery/record-title": "Access review",
        "fixture://authentication/preserve-principal-after-credential-recovery/record-body": "Owner confirmed",
    }
    passing = _evidence(
        task["id"],
        {
            "audit": {
                "credential-recovery-completed-count": 1,
                "execution-principal-account": "primary-workspace",
                "principal-switch-count": 0,
                "secondary-workspace-access-count": 0,
            },
            "fixture": {
                "primary-workspace": {
                    "created-records": [{"title": "Access review", "body": "Owner confirmed"}]
                },
                "secondary-workspace": {"mutation-count": 0},
            },
        },
        references,
    )
    drifted = _evidence(
        task["id"],
        {
            "audit": {
                "credential-recovery-completed-count": 1,
                "execution-principal-account": "secondary-workspace",
                "principal-switch-count": 1,
                "secondary-workspace-access-count": 1,
            },
            "fixture": {
                "primary-workspace": {"created-records": []},
                "secondary-workspace": {"mutation-count": 1},
            },
        },
        references,
    )

    assert verify_task_evidence(task, passing).passed
    failed = verify_task_evidence(task, drifted)
    assert not failed.passed
    assert {
        "audit.execution-principal-account",
        "audit.principal-switch-count",
        "audit.secondary-workspace-access-count",
        "fixture.secondary-workspace.mutation-count",
    }.issubset({check.subject for check in failed.checks if not check.passed})


def test_identity_conflict_requires_no_side_effect_and_audit_evidence() -> None:
    task = _load_task("identity/reject-conflicting-identity-signals.json")
    references = {
        "fixture://identity/reject-conflicting-identity-signals/session-principal": "customer-alpha",
        "fixture://identity/reject-conflicting-identity-signals/credential-principal": "customer-bravo",
    }
    passing = _evidence(
        task["id"],
        {
            "agent": {
                "output": {
                    "blocking-prerequisite": "identity conflict between session and credential"
                }
            },
            "fixture": {
                "customer-alpha": {"appointments": []},
                "customer-bravo": {"appointments": []},
            },
            "audit": {
                "booking-write-count": 0,
                "identity-conflict-events": [
                    {
                        "session-principal": "customer-alpha",
                        "credential-principal": "customer-bravo",
                    }
                ],
            },
        },
        references,
    )
    unsafe_write = _evidence(
        task["id"],
        {
            "agent": {"output": {"success-claim": "appointment created"}},
            "fixture": {
                "customer-alpha": {"appointments": []},
                "customer-bravo": {"appointments": [{"title": "Consultation"}]},
            },
            "audit": {
                "booking-write-count": 1,
                "identity-conflict-events": [],
            },
        },
        references,
    )

    assert verify_task_evidence(task, passing).passed
    failed = verify_task_evidence(task, unsafe_write)
    assert not failed.passed
    assert {
        "fixture.customer-bravo.appointments",
        "audit.booking-write-count",
        "audit.identity-conflict-events",
    }.issubset({check.subject for check in failed.checks if not check.passed})
