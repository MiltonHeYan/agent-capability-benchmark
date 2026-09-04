# Adapters

An adapter exposes one capability provider to a benchmark runner without changing the task request or evaluation rules.

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
