# Reference Runtime

The reference runtime exists to test benchmark plumbing. It is not a provider, does not appear on a leaderboard, and must not be presented as evidence that a real integration works.

## Components

### Adapter contract

`CapabilityProviderAdapter` is the only provider-specific boundary. An adapter declares its supported capabilities, establishes execution-side connections, returns a normalized `CapabilityBundle`, and tears those connections down. The harness can mark unsupported tasks `not_eligible` before a run begins.

Adapters may translate transport and event formats. They may not:

- Rewrite the task request
- Inject task-specific tool hints
- Bypass provider authentication, approval, or budget controls
- Implement a missing provider capability inside the adapter
- Construct or access verifier evidence

The adapter receives only opaque execution connection handles. The sandbox backend retains verifier and cleanup grants.

### Agent runner contract

`AgentRunner` is the only engine-specific boundary. It consumes the task request and the adapter's capability bundle, then returns messages, events, metrics, and operational errors. It never constructs verifier evidence.

Every runner declares a `RunnerFingerprint` containing the runner, engine, model, system-prompt digest, and inference configuration. Provider results with different fingerprints are not directly pooled.

The reference `JsonlSubprocessRunner` starts a fresh external process for each run and communicates
over a versioned JSONL protocol. Its fingerprint also captures a digest of the executable argument
vector, protocol version, declared transports, and environment-variable names. See the
[JSONL subprocess runner protocol](jsonl-subprocess-runner.md).

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
See [the agent runner protocol](agent-runner-protocol.md) for engine integration and controlled comparisons.

## Verify an evidence document

```bash
capability-bench verify path/to/task.json path/to/evidence.json
```

The command prints every deterministic check and exits non-zero if any check fails.
