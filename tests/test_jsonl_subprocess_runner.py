from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from agent_capability_benchmark.adapters.base import (
    CapabilityBundle,
    CapabilityProviderAdapter,
)
from agent_capability_benchmark.harness import IsolatedRunHarness
from agent_capability_benchmark.runners.base import AgentRunContext
from agent_capability_benchmark.runners.jsonl_subprocess import JsonlSubprocessRunner
from agent_capability_benchmark.sandbox import (
    CleanupReport,
    CredentialGrant,
    SandboxBackend,
    SandboxLease,
    VerificationSnapshot,
)

FAKE_AGENT = Path(__file__).parent / "fixtures" / "fake_jsonl_agent.py"
RUNTIME_DIGEST = "a" * 64


def _runner(
    mode: str,
    *,
    environment: dict[str, str] | None = None,
    grace: float = 0.2,
) -> JsonlSubprocessRunner:
    return JsonlSubprocessRunner(
        (sys.executable, str(FAKE_AGENT), mode),
        engine="fake-agent",
        engine_version="1.2.3",
        runtime_image_sha256=RUNTIME_DIGEST,
        model="fake-model",
        system_prompt="You are the fixed benchmark agent.",
        supported_transports=("mcp",),
        inference_config={"temperature": 0},
        environment=environment,
        termination_grace_seconds=grace,
    )


def _context(
    workspace: Path,
    *,
    timeout: float = 2,
    scripted_events: list[dict] | None = None,
) -> AgentRunContext:
    return AgentRunContext(
        task={
            "id": "read-known-record",
            "request": "Read the requested record.",
            "policy": {"approval": "not_required", "prohibited_actions": []},
            "limits": {"timeout_seconds": timeout, "max_tool_calls": 5, "max_retries": 1},
            "scripted_user_events": scripted_events or [],
        },
        run_id="run-12345678",
        workspace=workspace,
        namespace="acb-run-12345678",
        allowed_egress=("provider.invalid:443",),
    )


def _bundle(secret: str = "execution-handle-123") -> CapabilityBundle:
    return CapabilityBundle(
        transport="mcp",
        version="1",
        configuration={"connection": secret},
        tool_manifest=({"name": "records.read", "description": "Read a record"},),
    )


async def _run_once(
    runner: JsonlSubprocessRunner,
    context: AgentRunContext,
    bundle: CapabilityBundle | None = None,
):
    async with runner:
        await runner.setup(context, bundle or _bundle())
        return await runner.run(context)


def test_successful_run_normalizes_messages_tools_usage_and_identity(tmp_path: Path) -> None:
    runner = _runner("success")
    result = asyncio.run(_run_once(runner, _context(tmp_path)))

    assert result.completed_normally
    assert result.error is None
    assert result.messages == ({"role": "assistant", "content": "done"},)
    assert result.events[0]["name"] == "records.read"
    assert result.metrics["input_tokens"] == 10
    assert result.metrics["output_tokens"] == 4
    assert result.metrics["tool_calls"] == 1
    assert result.metadata["cwd"] == str(tmp_path)
    assert result.metadata["process_returncode"] == 0
    assert result.metadata["received"]["type"] == "run"
    assert result.metadata["received"]["runner"]["fingerprint_sha256"] == (
        runner.fingerprint.digest
    )


def test_each_run_uses_a_fresh_process_and_workspace(tmp_path: Path) -> None:
    runner = _runner("success")
    first_workspace = tmp_path / "first"
    second_workspace = tmp_path / "second"
    first_workspace.mkdir()
    second_workspace.mkdir()

    first = asyncio.run(_run_once(runner, _context(first_workspace)))
    second = asyncio.run(_run_once(runner, _context(second_workspace)))

    assert first.metadata["pid"] != second.metadata["pid"]
    assert first.metadata["cwd"] == str(first_workspace)
    assert second.metadata["cwd"] == str(second_workspace)


def test_multi_turn_scripted_events_are_matched_once_and_not_dropped(tmp_path: Path) -> None:
    scripted_events = [
        {
            "when": "on-valid-approval-request",
            "type": "approval",
            "value": "approve",
        },
        {
            "when": "on-clarification-request",
            "type": "clarification",
            "value": "Use the primary workspace.",
        },
    ]
    result = asyncio.run(
        _run_once(_runner("multi-turn"), _context(tmp_path, scripted_events=scripted_events))
    )

    assert result.completed_normally
    response_events = [event for event in result.events if event.get("status") == "received"]
    assert [event["response"]["event"]["value"] for event in response_events] == [
        "approve",
        "Use the primary workspace.",
    ]
    assert {event["request_id"] for event in result.events if "request_id" in event} == {
        "approval-1",
        "clarification-1",
    }


@pytest.mark.parametrize(
    ("mode", "error_code"),
    (("malformed", "malformed-jsonl-event"), ("early-exit", "early-exit")),
)
def test_protocol_failures_are_structured(tmp_path: Path, mode: str, error_code: str) -> None:
    result = asyncio.run(_run_once(_runner(mode), _context(tmp_path)))

    assert not result.completed_normally
    assert result.metadata["operational_errors"][0]["code"] == error_code
    assert result.error
    if mode == "early-exit":
        assert result.metadata["process_returncode"] == 7
        assert "engine failed before final" in result.metadata["stderr"]


def test_timeout_terminates_and_reaps_an_uncooperative_child(tmp_path: Path) -> None:
    runner = _runner("hang", grace=0.05)
    result = asyncio.run(_run_once(runner, _context(tmp_path, timeout=0.05)))

    assert not result.completed_normally
    assert result.metadata["operational_errors"][0]["code"] == "timeout"
    assert result.metadata["process_returncode"] is not None
    assert runner.process_returncode is not None


def test_cancellation_terminates_and_reaps_the_child(tmp_path: Path) -> None:
    runner = _runner("hang", grace=0.05)
    context = _context(tmp_path, timeout=10)

    async def cancel_run() -> None:
        await runner.setup(context, _bundle())
        task = asyncio.create_task(runner.run(context))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await runner.teardown(context)

    asyncio.run(cancel_run())
    assert runner.process_returncode is not None


def test_secrets_are_redacted_from_all_normalized_child_output(tmp_path: Path) -> None:
    execution_secret = "execution-handle-very-secret"
    environment_secret = "engine-token-very-secret"
    result = asyncio.run(
        _run_once(
            _runner("leak", environment={"ENGINE_API_TOKEN": environment_secret}),
            _context(tmp_path),
            _bundle(execution_secret),
        )
    )
    serialized = json.dumps(
        {
            "messages": result.messages,
            "events": result.events,
            "error": result.error,
            "metadata": result.metadata,
        }
    )

    assert execution_secret not in serialized
    assert environment_secret not in serialized
    assert "[REDACTED]" in serialized


def test_fingerprint_changes_when_driver_command_or_environment_shape_changes() -> None:
    baseline = _runner("success").fingerprint.digest

    assert _runner("early-exit").fingerprint.digest != baseline
    assert _runner("success", environment={"ENGINE_MODE": "test"}).fingerprint.digest != baseline


class _Adapter(CapabilityProviderAdapter):
    name = "fixture-provider"
    capabilities = frozenset({"record-read"})

    async def setup(self, context):
        return _bundle(context.execution_connections["records"])

    async def teardown(self, context):
        return None


class _Sandbox(SandboxBackend):
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def provision(self, task, run_id):
        return SandboxLease(
            run_id=run_id,
            namespace=f"acb-{run_id}",
            workspace=self.workspace,
            fixture_base_url="http://127.0.0.1:8765",
            execution_grants={"records": CredentialGrant("execution-handle-123", "execution-user")},
            verifier_grants={"records": CredentialGrant("verifier-handle-456", "verifier-user")},
        )

    async def capture_baseline(self, lease, task):
        return VerificationSnapshot(observations={}, references={"expected": True})

    async def capture_final_state(self, lease, task):
        return VerificationSnapshot(observations={"fixture": {"ok": True}})

    async def cleanup(self, lease):
        return CleanupReport(succeeded=True)


def test_harness_keeps_hidden_task_fields_and_verifier_credentials_from_child(
    tmp_path: Path,
) -> None:
    task = {
        "id": "read-known-record",
        "version": "0.1.0",
        "title": "Read a known record",
        "track": "core",
        "request": "Read the requested record.",
        "capabilities_required": ["record-read"],
        "fixture": {"kind": "records", "metadata": {"hidden": "fixture-secret"}},
        "policy": {"approval": "not_required", "prohibited_actions": []},
        "limits": {"timeout_seconds": 2, "max_tool_calls": 5, "max_retries": 1},
        "expected_outcome": {"primary_verdict": "verified_success", "reason_code": "ok"},
        "verifier": {"checks": [{"subject": "fixture.ok", "operator": "equals", "expected": True}]},
    }
    result = asyncio.run(
        IsolatedRunHarness(_Sandbox(tmp_path)).run(
            task,
            _Adapter(),
            _runner("success"),
            run_id="run-12345678",
        )
    )
    received = result.agent_result.metadata["received"]
    serialized = json.dumps(received)

    assert "expected_outcome" not in received["task"]
    assert "verifier" not in received["task"]
    assert "fixture-secret" not in serialized
    assert "verifier-handle-456" not in serialized
    assert "execution-handle-123" not in serialized
    assert "[REDACTED]" in serialized


def test_protocol_failure_still_allows_final_state_verification_and_cleanup(
    tmp_path: Path,
) -> None:
    sandbox = _Sandbox(tmp_path)
    task = {
        "id": "read-known-record",
        "version": "0.1.0",
        "title": "Read a known record",
        "track": "core",
        "request": "Read the requested record.",
        "capabilities_required": ["record-read"],
        "fixture": {"kind": "records"},
        "policy": {"approval": "not_required", "prohibited_actions": []},
        "limits": {"timeout_seconds": 2, "max_tool_calls": 5, "max_retries": 1},
        "expected_outcome": {"primary_verdict": "verified_success", "reason_code": "ok"},
        "verifier": {"checks": [{"subject": "fixture.ok", "operator": "equals", "expected": True}]},
    }

    result = asyncio.run(
        IsolatedRunHarness(sandbox).run(
            task,
            _Adapter(),
            _runner("malformed"),
            run_id="run-12345678",
        )
    )

    assert result.verification.passed
    assert result.cleanup.succeeded
    assert not result.agent_result.completed_normally
    assert result.agent_result.metadata["operational_errors"][0]["code"] == (
        "malformed-jsonl-event"
    )
