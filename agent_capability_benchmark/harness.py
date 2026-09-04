from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from agent_capability_benchmark.adapters.base import (
    AdapterRunResult,
    CapabilityProviderAdapter,
)
from agent_capability_benchmark.evidence import validate_evidence
from agent_capability_benchmark.sandbox import CleanupReport, SandboxBackend, SandboxLease
from agent_capability_benchmark.verifier import VerificationResult, verify_task_evidence


class NotEligibleError(ValueError):
    pass


@dataclass(frozen=True)
class IsolatedRunResult:
    task_id: str
    run_id: str
    evidence: dict[str, Any]
    verification: VerificationResult
    adapter_result: AdapterRunResult
    cleanup: CleanupReport


class IsolatedRunHarness:
    """Execute one provider attempt without exposing verifier credentials."""

    def __init__(self, sandbox: SandboxBackend) -> None:
        self.sandbox = sandbox

    async def run(
        self,
        task: dict[str, Any],
        adapter: CapabilityProviderAdapter,
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
            context = lease.adapter_context(task)

            adapter_result = AdapterRunResult()
            adapter_errors: list[str] = []
            try:
                async with adapter:
                    try:
                        await adapter.setup(context)
                    except Exception as error:
                        adapter_errors.append(_format_adapter_error("setup", error))
                    else:
                        try:
                            adapter_result = await adapter.run(context)
                        except Exception as error:  # the external write may still have succeeded
                            adapter_errors.append(_format_adapter_error("run", error))
                    finally:
                        try:
                            await adapter.teardown(context)
                        except Exception as error:
                            adapter_errors.append(_format_adapter_error("teardown", error))
            except Exception as error:
                adapter_errors.append(_format_adapter_error("lifecycle", error))
            finally:
                final = await self.sandbox.capture_final_state(lease, task)

            if adapter_errors:
                reported_errors = [
                    error for error in (adapter_result.error, *adapter_errors) if error
                ]
                adapter_result = AdapterRunResult(
                    completed_normally=False,
                    error="; ".join(reported_errors),
                    events=adapter_result.events,
                    metadata=adapter_result.metadata,
                )

            evidence = {
                "task_id": task["id"],
                "run_id": actual_run_id,
                "observations": final.observations,
                "baseline": baseline.observations,
                "references": baseline.references,
                "events": [
                    *final.events,
                    *({"source": "adapter", "payload": event} for event in adapter_result.events),
                ],
                "metadata": {
                    **adapter_result.metadata,
                    "adapter": adapter.name,
                    "adapter_completed_normally": adapter_result.completed_normally,
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
                adapter_result=adapter_result,
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
            adapter_result=result.adapter_result,
            cleanup=cleanup_report,
        )


def _format_adapter_error(phase: str, error: Exception) -> str:
    return f"{phase} {type(error).__name__}: {error}"
