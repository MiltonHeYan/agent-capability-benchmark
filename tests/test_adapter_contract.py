from __future__ import annotations

from agent_capability_benchmark.adapters.base import CapabilityProviderAdapter


class ExampleAdapter(CapabilityProviderAdapter):
    name = "example"
    capabilities = frozenset({"record-read", "connected-account-read"})

    async def setup(self, context):
        return None

    async def run(self, context):
        raise NotImplementedError

    async def teardown(self, context):
        return None


def test_adapter_capability_gating() -> None:
    supported_task = {"capabilities_required": ["record-read", "connected-account-read"]}
    unsupported_task = {"capabilities_required": ["record-read", "record-create"]}

    assert ExampleAdapter.supports(supported_task)
    assert not ExampleAdapter.supports(unsupported_task)
    assert ExampleAdapter.missing_capabilities(unsupported_task) == frozenset({"record-create"})
