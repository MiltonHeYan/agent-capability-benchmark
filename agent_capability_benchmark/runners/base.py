from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agent_capability_benchmark.adapters.base import CapabilityBundle


@dataclass(frozen=True)
class RunnerFingerprint:
    """Every agent-side variable that must remain fixed in a provider comparison."""

    runner: str
    runner_version: str
    engine: str
    engine_version: str
    runtime_image_sha256: str
    model: str
    system_prompt_sha256: str
    inference_config: dict[str, Any] = field(default_factory=dict)
    driver_config_sha256: str | None = None

    def __post_init__(self) -> None:
        required = (
            self.runner,
            self.runner_version,
            self.engine,
            self.engine_version,
            self.model,
        )
        if not all(value.strip() for value in required):
            raise ValueError("runner fingerprint fields must not be empty")
        _validate_sha256("runtime_image_sha256", self.runtime_image_sha256)
        _validate_sha256("system_prompt_sha256", self.system_prompt_sha256)
        if self.driver_config_sha256 is not None:
            _validate_sha256("driver_config_sha256", self.driver_config_sha256)

    @classmethod
    def from_system_prompt(
        cls,
        *,
        runner: str,
        runner_version: str,
        engine: str,
        engine_version: str,
        runtime_image_sha256: str,
        model: str,
        system_prompt: str,
        inference_config: dict[str, Any] | None = None,
        driver_config_sha256: str | None = None,
    ) -> RunnerFingerprint:
        return cls(
            runner=runner,
            runner_version=runner_version,
            engine=engine,
            engine_version=engine_version,
            runtime_image_sha256=runtime_image_sha256,
            model=model,
            system_prompt_sha256=hashlib.sha256(system_prompt.encode()).hexdigest(),
            inference_config=inference_config or {},
            driver_config_sha256=driver_config_sha256,
        )

    @property
    def digest(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


def _validate_sha256(field_name: str, value: str) -> None:
    if len(value) != 64 or value != value.lower():
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as error:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest") from error


@dataclass(frozen=True)
class AgentRunContext:
    task: dict[str, Any]
    run_id: str
    workspace: Path
    namespace: str
    allowed_egress: tuple[str, ...]


@dataclass(frozen=True)
class AgentRunResult:
    completed_normally: bool = True
    error: str | None = None
    messages: tuple[dict[str, Any], ...] = ()
    events: tuple[dict[str, Any], ...] = ()
    metrics: dict[str, int | float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRunner(ABC):
    """Engine-specific driver held constant while providers are compared."""

    fingerprint: RunnerFingerprint
    supported_transports: frozenset[str] = frozenset()

    def supports(self, bundle: CapabilityBundle) -> bool:
        return bundle.transport in self.supported_transports

    async def __aenter__(self) -> AgentRunner:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    @abstractmethod
    async def setup(self, context: AgentRunContext, bundle: CapabilityBundle) -> None:
        """Start a clean, pinned engine session and attach the capability bundle."""

    @abstractmethod
    async def run(self, context: AgentRunContext) -> AgentRunResult:
        """Deliver the task request and return normalized agent-side telemetry."""

    @abstractmethod
    async def teardown(self, context: AgentRunContext) -> None:
        """Stop the engine session and release runner-owned resources."""
