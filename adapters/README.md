# Adapters

An adapter exposes one capability provider to a benchmark runner without changing the task request or evaluation rules.

The adapter receives only run-scoped, opaque execution connection handles. Its setup returns a normalized `CapabilityBundle` for the fixed agent runner. It must not execute the task, receive verifier or cleanup credentials, access baseline snapshots or hidden expected values, or access the evidence store. The trusted harness collects final state independently after the agent returns, times out, or raises an error.

Each adapter will declare:

- Adapter and provider configuration versions
- Supported benchmark tracks
- Setup and credential requirements
- Capability discovery mechanism
- Execution interface
- Observable usage, latency, and cost fields
- Redaction rules for traces

Adapters may normalize transport and event formats. They must not rewrite task prompts, bypass provider safety controls, inject task-specific hints, or implement missing provider capabilities inside the adapter.

Published comparisons must use reviewable adapter source and pin an exact commit.

The executable adapter contract lives in `agent_capability_benchmark/adapters/base.py`. See `docs/reference-runtime.md` for lifecycle and evidence requirements.
