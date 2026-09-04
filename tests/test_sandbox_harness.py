from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from agent_capability_benchmark.adapters.base import (
    AdapterRunResult,
    CapabilityProviderAdapter,
)
from agent_capability_benchmark.harness import IsolatedRunHarness
from agent_capability_benchmark.sandbox import (
    CleanupReport,
    CredentialGrant,
    SandboxBackend,
    SandboxLease,
    VerificationSnapshot,
)


class RecordingAdapter(CapabilityProviderAdapter):
    name = "recording"
    capabilities = frozenset({"record-create"})

    def __init__(self, backend: FakeSandbox) -> None:
        self.backend = backend
        self.seen_context = None

    async def setup(self, context):
        self.seen_context = context

    async def run(self, context):
        self.backend.created = True
        return AdapterRunResult(metadata={"transport": "fixture"})

    async def teardown(self, context):
        return None


class FailingAfterWriteAdapter(RecordingAdapter):
    name = "failing-after-write"

    async def run(self, context):
        self.backend.created = True
        raise TimeoutError("provider response was lost")


class FakeSandbox(SandboxBackend):
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.created = False
        self.cleaned = False

    async def provision(self, task, run_id):
        return SandboxLease(
            run_id=run_id,
            namespace=f"acb-{run_id}",
            workspace=self.workspace,
            fixture_base_url="http://127.0.0.1:8765",
            execution_grants={
                "records": CredentialGrant("exec-handle", "execution-user", frozenset({"write"}))
            },
            verifier_grants={
                "records": CredentialGrant("verify-handle", "verifier-user", frozenset({"read"}))
            },
            allowed_egress=("fixture.invalid:443",),
        )

    async def capture_baseline(self, lease, task):
        return VerificationSnapshot(
            observations={"fixture": {"created": False}},
            references={"expected_created": True},
        )

    async def capture_final_state(self, lease, task):
        return VerificationSnapshot(observations={"fixture": {"created": self.created}})

    async def cleanup(self, lease):
        self.cleaned = True
        return CleanupReport(succeeded=True)


def _task() -> dict:
    return {
        "id": "create-record",
        "capabilities_required": ["record-create"],
        "verifier": {
            "checks": [
                {
                    "subject": "fixture.created",
                    "operator": "equals",
                    "expected_ref": "expected_created",
                }
            ]
        },
    }


def test_lease_rejects_shared_execution_and_verifier_principal(tmp_path: Path) -> None:
    lease = SandboxLease(
        run_id="run-12345678",
        namespace="acb-run-12345678",
        workspace=tmp_path,
        fixture_base_url="http://127.0.0.1:8765",
        execution_grants={"service": CredentialGrant("exec", "same-user")},
        verifier_grants={"service": CredentialGrant("verify", "same-user")},
    )

    with pytest.raises(ValueError, match="must be distinct"):
        lease.validate()


def test_harness_exposes_only_execution_handles_and_cleans_up(tmp_path: Path) -> None:
    sandbox = FakeSandbox(tmp_path)
    adapter = RecordingAdapter(sandbox)

    result = asyncio.run(IsolatedRunHarness(sandbox).run(_task(), adapter, run_id="run-12345678"))

    assert result.verification.passed
    assert result.cleanup.succeeded
    assert sandbox.cleaned
    assert adapter.seen_context.execution_connections == {"records": "exec-handle"}
    assert "verify-handle" not in repr(adapter.seen_context)


def test_external_state_is_verified_after_adapter_timeout(tmp_path: Path) -> None:
    sandbox = FakeSandbox(tmp_path)
    adapter = FailingAfterWriteAdapter(sandbox)

    result = asyncio.run(IsolatedRunHarness(sandbox).run(_task(), adapter, run_id="run-12345678"))

    assert result.verification.passed
    assert not result.adapter_result.completed_normally
    assert "TimeoutError" in result.adapter_result.error
    assert result.cleanup.succeeded
