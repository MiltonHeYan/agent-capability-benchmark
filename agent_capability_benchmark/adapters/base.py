from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar


@dataclass
class AdapterContext:
    task: dict[str, Any]
    run_id: str
    fixture_base_url: str
    workspace: Path | None = None
    namespace: str = ""
    execution_connections: dict[str, str] = field(default_factory=dict)
    allowed_egress: tuple[str, ...] = ()
    adapter_state: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterRunResult:
    completed_normally: bool = True
    error: str | None = None
    events: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class CapabilityProviderAdapter(ABC):
    """Provider-specific boundary used by the benchmark harness.

    Adapters translate a neutral task into the provider's normal discovery,
    connection, and execution flow. They must not rewrite the user request,
    inject task-specific hints, or implement missing provider capabilities.
    """

    name: ClassVar[str] = ""
    capabilities: ClassVar[frozenset[str]] = frozenset()

    @classmethod
    def missing_capabilities(cls, task: dict[str, Any]) -> frozenset[str]:
        required = frozenset(task.get("capabilities_required", []))
        return required - cls.capabilities

    @classmethod
    def supports(cls, task: dict[str, Any]) -> bool:
        return not cls.missing_capabilities(task)

    async def __aenter__(self) -> CapabilityProviderAdapter:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    @abstractmethod
    async def setup(self, context: AdapterContext) -> None:
        """Create provider-side session state and connect fixture accounts."""

    @abstractmethod
    async def run(self, context: AdapterContext) -> AdapterRunResult:
        """Execute the task without observing or constructing verifier evidence."""

    @abstractmethod
    async def teardown(self, context: AdapterContext) -> None:
        """Release provider-side state created for the run."""
