from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_capability_benchmark.adapters.base import AdapterContext

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")


@dataclass(frozen=True)
class CredentialGrant:
    """A non-secret description of a credential held by the control plane."""

    handle: str
    principal_id: str
    scopes: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.handle:
            raise ValueError("credential handle must not be empty")
        if not self.principal_id:
            raise ValueError("credential principal_id must not be empty")


@dataclass(frozen=True)
class SandboxLease:
    """Resources reserved for one run.

    Credential grants contain opaque handles, never access tokens. Only execution
    handles are projected into AdapterContext; verifier and cleanup handles remain
    private to the sandbox backend.
    """

    run_id: str
    namespace: str
    workspace: Path
    fixture_base_url: str
    execution_grants: dict[str, CredentialGrant]
    verifier_grants: dict[str, CredentialGrant]
    cleanup_grants: dict[str, CredentialGrant] = field(default_factory=dict)
    allowed_egress: tuple[str, ...] = ()
    expires_at: datetime | None = None

    def validate(self) -> None:
        if not _RUN_ID_PATTERN.fullmatch(self.run_id):
            raise ValueError("run_id must be 8-128 URL-safe characters")
        if not self.namespace or self.run_id not in self.namespace:
            raise ValueError("sandbox namespace must include the complete run_id")
        if not self.workspace.is_absolute():
            raise ValueError("sandbox workspace must be an absolute path")
        if not self.workspace.is_dir():
            raise ValueError("sandbox workspace must exist and be a directory")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("sandbox expiry must be timezone-aware")

        execution_principals = {grant.principal_id for grant in self.execution_grants.values()}
        verifier_principals = {grant.principal_id for grant in self.verifier_grants.values()}
        overlap = execution_principals & verifier_principals
        if overlap:
            joined = ", ".join(sorted(overlap))
            raise ValueError(f"execution and verifier principals must be distinct: {joined}")

        all_handles = [
            grant.handle
            for grants in (self.execution_grants, self.verifier_grants, self.cleanup_grants)
            for grant in grants.values()
        ]
        if len(all_handles) != len(set(all_handles)):
            raise ValueError("credential handles must be unique across control-plane roles")

        for target in self.allowed_egress:
            if not target or target == "*":
                raise ValueError("egress targets must be explicit and non-empty")

    def adapter_context(self, task: dict[str, Any]) -> AdapterContext:
        self.validate()
        return AdapterContext(
            task=task,
            run_id=self.run_id,
            fixture_base_url=self.fixture_base_url,
            workspace=self.workspace,
            namespace=self.namespace,
            execution_connections={
                name: grant.handle for name, grant in self.execution_grants.items()
            },
            allowed_egress=self.allowed_egress,
        )


@dataclass(frozen=True)
class VerificationSnapshot:
    observations: dict[str, Any]
    references: dict[str, Any] = field(default_factory=dict)
    events: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class CleanupReport:
    succeeded: bool
    residual_resources: tuple[str, ...] = ()
    detail: str = ""


class SandboxBackend(ABC):
    """Control-plane boundary for runner, tenant, credentials, and verification."""

    @abstractmethod
    async def provision(self, task: dict[str, Any], run_id: str) -> SandboxLease:
        """Allocate a fresh runner state and external test-tenant namespace."""

    @abstractmethod
    async def capture_baseline(
        self,
        lease: SandboxLease,
        task: dict[str, Any],
    ) -> VerificationSnapshot:
        """Observe initial state using verifier credentials."""

    @abstractmethod
    async def capture_final_state(
        self,
        lease: SandboxLease,
        task: dict[str, Any],
    ) -> VerificationSnapshot:
        """Observe final state using verifier credentials."""

    @abstractmethod
    async def cleanup(self, lease: SandboxLease) -> CleanupReport:
        """Delete run-scoped external and local resources."""
