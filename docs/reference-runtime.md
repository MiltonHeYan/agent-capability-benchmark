# Reference Runtime

The reference runtime exists to test benchmark plumbing. It is not a provider, does not appear on a leaderboard, and must not be presented as evidence that a real integration works.

## Components

### Adapter contract

`CapabilityProviderAdapter` is the only provider-specific boundary. An adapter declares its supported capabilities and implements setup, execution, and teardown. The harness can mark unsupported tasks `not_eligible` before a run begins.

Adapters may translate transport and event formats. They may not:

- Rewrite the task request
- Inject task-specific tool hints
- Bypass provider authentication, approval, or budget controls
- Implement a missing provider capability inside the adapter
- Construct or access verifier evidence

The adapter receives only opaque execution connection handles. The sandbox backend retains verifier and cleanup grants.

### Normalized evidence

A run evidence document is constructed by the trusted harness, not returned by the adapter. It contains:

- `task_id` and unique `run_id`
- Final normalized `observations`
- An immutable `baseline` captured before execution
- Fixture reference values used by deterministic checks
- An optional event stream and run metadata

Evidence validates against `spec/evidence.schema.json`.

### Verifier engine

The verifier resolves each task's structured checks against normalized evidence. Supported operators are:

- `equals`
- `contains`
- `count-equals`
- `exists`
- `not-exists`
- `unchanged`
- `less-than-or-equal`

A run passes deterministic verification only when every check passes. A semantic model cannot override a failed deterministic check.

### Fixture session server

The reference fixture server provides isolated session creation, immutable baseline capture, observation updates, event collection, evidence reads, and session deletion.

It intentionally binds only to loopback. Start it with:

```bash
capability-bench serve-fixtures --port 8765
```

The observation update endpoint is for harness conformance testing. Real provider evaluations must collect state through independent verifier credentials and must not give the provider or agent access to verifier state.

See [the sandbox and test-tenant model](sandbox-and-tenancy.md) for the production trust boundaries and run lifecycle.

## Verify an evidence document

```bash
capability-bench verify path/to/task.json path/to/evidence.json
```

The command prints every deterministic check and exits non-zero if any check fails.
