from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from agent_capability_benchmark.adapters.base import CapabilityBundle, CapabilityProviderAdapter
from agent_capability_benchmark.evidence import validate_evidence
from agent_capability_benchmark.runners.base import AgentRunContext, AgentRunner, AgentRunResult
from agent_capability_benchmark.sandbox import CleanupReport, SandboxBackend, SandboxLease
from agent_capability_benchmark.verifier import VerificationResult, verify_task_evidence


class NotEligibleError(ValueError):
    pass


class RunnerCompatibilityError(ValueError):
    pass


@dataclass(frozen=True)
class IsolatedRunResult:
    task_id: str
    run_id: str
    evidence: dict[str, Any]
    verification: VerificationResult
    agent_result: AgentRunResult
    adapter_errors: tuple[str, ...]
    cleanup: CleanupReport


class IsolatedRunHarness:
    """Run a fixed agent against one provider without exposing verifier state."""

    def __init__(self, sandbox: SandboxBackend) -> None:
        self.sandbox = sandbox

    async def run(
        self,
        task: dict[str, Any],
        adapter: CapabilityProviderAdapter,
        runner: AgentRunner,
        *,
        run_id: str | None = None,
    ) -> IsolatedRunResult:
        missing = adapter.missing_capabilities(task)
        if missing:
            raise NotEligibleError(
                f"adapter {adapter.name!r} is missing capabilities: {', '.join(sorted(missing))}"
            )

        actual_run_id = run_id or str(uuid4())
        lease: SandboxLease | None = None
        cleanup_report = CleanupReport(succeeded=False, detail="cleanup did not run")
        result: IsolatedRunResult | None = None

        try:
            lease = await self.sandbox.provision(task, actual_run_id)
            if lease.run_id != actual_run_id:
                raise ValueError("sandbox lease run_id does not match requested run_id")
            lease.validate()
            baseline = await self.sandbox.capture_baseline(lease, task)
            adapter_context = lease.adapter_context(_adapter_task_view(task))
            agent_context = AgentRunContext(
                task=_agent_task_view(task),
                run_id=lease.run_id,
                workspace=lease.workspace,
                namespace=lease.namespace,
                allowed_egress=lease.allowed_egress,
            )

            adapter_errors: list[str] = []
            bundle: CapabilityBundle | None = None
            agent_result = AgentRunResult(
                completed_normally=False,
                error="agent did not start because provider setup failed",
            )
            try:
                async with adapter:
                    try:
                        candidate_bundle = await adapter.setup(adapter_context)
                        if not isinstance(candidate_bundle, CapabilityBundle):
                            raise TypeError("adapter setup must return CapabilityBundle")
                        bundle = candidate_bundle
                    except Exception as error:
                        adapter_errors.append(_format_error("adapter setup", error))
                    else:
                        if not runner.supports(bundle):
                            raise RunnerCompatibilityError(
                                f"runner {runner.fingerprint.runner!r} does not support "
                                f"transport {bundle.transport!r}"
                            )
                        agent_result = await _execute_agent(runner, agent_context, bundle)
                    finally:
                        try:
                            await adapter.teardown(adapter_context)
                        except Exception as error:
                            adapter_errors.append(_format_error("adapter teardown", error))
            except RunnerCompatibilityError:
                raise
            except Exception as error:
                adapter_errors.append(_format_error("adapter lifecycle", error))
            finally:
                final = await self.sandbox.capture_final_state(lease, task)

            evidence = {
                "task_id": task["id"],
                "run_id": actual_run_id,
                "observations": final.observations,
                "baseline": baseline.observations,
                "references": baseline.references,
                "events": [
                    *final.events,
                    *({"source": "agent", "payload": event} for event in agent_result.events),
                ],
                "metadata": {
                    **agent_result.metadata,
                    "adapter": adapter.name,
                    "adapter_errors": adapter_errors,
                    "agent_completed_normally": agent_result.completed_normally,
                    "capability_transport": bundle.transport if bundle else None,
                    "capability_bundle_version": bundle.version if bundle else None,
                    "runner_fingerprint": asdict(runner.fingerprint),
                    "runner_fingerprint_sha256": runner.fingerprint.digest,
                },
            }
            evidence_errors = validate_evidence(evidence)
            if evidence_errors:
                raise ValueError("invalid collected evidence: " + "; ".join(evidence_errors))
            verification = verify_task_evidence(task, evidence)
            result = IsolatedRunResult(
                task_id=task["id"],
                run_id=actual_run_id,
                evidence=evidence,
                verification=verification,
                agent_result=agent_result,
                adapter_errors=tuple(adapter_errors),
                cleanup=cleanup_report,
            )
        finally:
            if lease is not None:
                cleanup_report = await self.sandbox.cleanup(lease)

        if result is None:
            raise AssertionError("run ended without a result")
        return IsolatedRunResult(
            task_id=result.task_id,
            run_id=result.run_id,
            evidence=result.evidence,
            verification=result.verification,
            agent_result=result.agent_result,
            adapter_errors=result.adapter_errors,
            cleanup=cleanup_report,
        )


async def _execute_agent(
    runner: AgentRunner,
    context: AgentRunContext,
    bundle: CapabilityBundle,
) -> AgentRunResult:
    agent_result = AgentRunResult(completed_normally=False, error="agent did not run")
    errors: list[str] = []
    try:
        async with runner:
            try:
                await runner.setup(context, bundle)
            except Exception as error:
                errors.append(_format_error("runner setup", error))
            else:
                try:
                    agent_result = await runner.run(context)
                except Exception as error:
                    errors.append(_format_error("runner run", error))
            finally:
                try:
                    await runner.teardown(context)
                except Exception as error:
                    errors.append(_format_error("runner teardown", error))
    except Exception as error:
        errors.append(_format_error("runner lifecycle", error))

    if not errors:
        return agent_result
    reported = [error for error in (agent_result.error, *errors) if error]
    return AgentRunResult(
        completed_normally=False,
        error="; ".join(reported),
        messages=agent_result.messages,
        events=agent_result.events,
        metrics=agent_result.metrics,
        metadata=agent_result.metadata,
    )


def _agent_task_view(task: dict[str, Any]) -> dict[str, Any]:
    visible = ("id", "version", "title", "track", "request", "policy", "limits", "tags")
    return {key: deepcopy(task[key]) for key in visible if key in task}


def _adapter_task_view(task: dict[str, Any]) -> dict[str, Any]:
    fixture = task.get("fixture", {})
    return {
        "capabilities_required": list(task.get("capabilities_required", [])),
        "fixture": {"kind": fixture["kind"]} if "kind" in fixture else {},
        "policy": dict(task.get("policy", {})),
        "limits": dict(task.get("limits", {})),
    }


def _format_error(phase: str, error: Exception) -> str:
    return f"{phase} {type(error).__name__}: {error}"
