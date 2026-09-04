from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from agent_capability_benchmark.adapters.base import (
    CapabilityBundle,
    CapabilityProviderAdapter,
)
from agent_capability_benchmark.harness import IsolatedRunHarness, RunnerCompatibilityError
from agent_capability_benchmark.runners.base import (
    AgentRunner,
    AgentRunResult,
    RunnerFingerprint,
)
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

    def __init__(self) -> None:
        self.seen_context = None

    async def setup(self, context):
        self.seen_context = context
        return CapabilityBundle(
            transport="mcp",
            version="1",
            configuration={"connection": context.execution_connections["records"]},
        )

    async def teardown(self, context):
        return None


class RecordingRunner(AgentRunner):
    fingerprint = RunnerFingerprint.from_system_prompt(
        runner="reference-streaming-runner",
        runner_version="1.0.0",
        engine="reference-agent",
        engine_version="1.2.3",
        runtime_image_sha256="a" * 64,
        model="reference-model-1",
        system_prompt="You are the fixed reference agent.",
        inference_config={"temperature": 0},
    )
    supported_transports = frozenset({"mcp"})

    def __init__(self, backend: FakeSandbox) -> None:
        self.backend = backend
        self.seen_context = None
        self.seen_bundle = None

    async def setup(self, context, bundle):
        self.seen_context = context
        self.seen_bundle = bundle

    async def run(self, context):
        self.backend.created = True
        return AgentRunResult(metadata={"transport": "fixture"})

    async def teardown(self, context):
        return None


class FailingAfterWriteRunner(RecordingRunner):
    async def run(self, context):
        self.backend.created = True
        raise TimeoutError("agent response was lost")


class UnsupportedTransportRunner(RecordingRunner):
    supported_transports = frozenset({"stdio"})


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
        "version": "1.0.0",
        "title": "Create a record",
        "track": "core",
        "request": "Create the requested record.",
        "capabilities_required": ["record-create"],
        "fixture": {
            "kind": "records",
            "reset_ref": "hidden",
            "seed_ref": "hidden",
            "metadata": {"hidden_value": "do-not-expose"},
        },
        "policy": {"approval": "not_required", "prohibited_actions": []},
        "limits": {"timeout_seconds": 60, "max_tool_calls": 10, "max_retries": 1},
        "expected_outcome": {
            "primary_verdict": "verified_success",
            "reason_code": "record-created",
        },
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


def test_harness_separates_agent_provider_and_verifier_views(tmp_path: Path) -> None:
    sandbox = FakeSandbox(tmp_path)
    adapter = RecordingAdapter()
    runner = RecordingRunner(sandbox)

    result = asyncio.run(
        IsolatedRunHarness(sandbox).run(_task(), adapter, runner, run_id="run-12345678")
    )

    assert result.verification.passed
    assert result.cleanup.succeeded
    assert sandbox.cleaned
    assert adapter.seen_context.execution_connections == {"records": "exec-handle"}
    assert "verify-handle" not in repr(adapter.seen_context)
    assert "request" not in adapter.seen_context.task
    assert "hidden_value" not in repr(adapter.seen_context.task)
    assert "verifier" not in runner.seen_context.task
    assert "expected_outcome" not in runner.seen_context.task
    assert not hasattr(runner.seen_context, "fixture_base_url")
    assert runner.seen_bundle.transport == "mcp"
    assert result.evidence["metadata"]["runner_fingerprint_sha256"] == runner.fingerprint.digest


def test_external_state_is_verified_after_agent_timeout(tmp_path: Path) -> None:
    sandbox = FakeSandbox(tmp_path)
    adapter = RecordingAdapter()
    runner = FailingAfterWriteRunner(sandbox)

    result = asyncio.run(
        IsolatedRunHarness(sandbox).run(_task(), adapter, runner, run_id="run-12345678")
    )

    assert result.verification.passed
    assert not result.agent_result.completed_normally
    assert "TimeoutError" in result.agent_result.error
    assert result.cleanup.succeeded


def test_incompatible_runner_is_rejected_and_sandbox_is_cleaned(tmp_path: Path) -> None:
    sandbox = FakeSandbox(tmp_path)
    adapter = RecordingAdapter()
    runner = UnsupportedTransportRunner(sandbox)

    with pytest.raises(RunnerCompatibilityError, match="does not support transport"):
        asyncio.run(
            IsolatedRunHarness(sandbox).run(_task(), adapter, runner, run_id="run-12345678")
        )

    assert sandbox.cleaned
