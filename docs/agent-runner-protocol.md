# Agent Runner Protocol

The benchmark can host multiple agent engines without making the agent an uncontrolled variable. Agent integration and provider integration are separate boundaries:

```text
task request ──► AgentRunner ──► CapabilityBundle ──► provider
                     │                                  │
                     └──── messages and tool events ────┘

trusted sandbox backend ──► baseline / final state ──► verifier
```

The provider adapter establishes execution-side connections and returns a `CapabilityBundle`. It does not execute the task. The fixed `AgentRunner` consumes the bundle and performs the task. Neither component can access verifier credentials or hidden expected values.

The runner is not given the fixture control URL. The agent reaches the external test system only through the capability bundle supplied by the provider adapter; network policy independently blocks undeclared bypass paths.

## Official comparison rule

The provider main track changes only the provider configuration and its adapter. Every other experimental input is fixed:

- runner implementation and version;
- agent engine and executable version;
- model identifier or immutable snapshot;
- system-prompt digest;
- inference settings;
- task request and scripted user behavior;
- capability transport presented to the runner;
- sandbox image and workspace seed;
- account permissions and fixture state;
- time, token, tool-call, retry, and spending limits;
- harness, verifier, and task-set versions.

`RunnerFingerprint` serializes the runner, engine, runtime-image digest, model, system-prompt digest, and inference settings, then produces a stable SHA-256 digest. Results with different fingerprints are not pooled into one provider comparison. The capability transport and bundle version are recorded alongside it and must also remain fixed within a comparison block.

## Multiple agent engines

Multiple engines are evaluated as pre-registered blocks, not freely selected per provider:

```text
runner A × every eligible provider
runner B × every eligible provider
runner C × every eligible provider
```

Each cell retains its own result. Cross-runner aggregates must publish their runner set, weighting, missing-cell policy, mean, minimum, and variance. A provider may not choose a preferred runner for the official main-track score.

Open combinations belong in a separate track. They compare the complete agent-model-provider configuration and must not be presented as a provider-only ranking.

## Runner lifecycle

1. Provision a clean workspace and external test-tenant lease.
2. Capture the verifier baseline.
3. Ask the provider adapter for a run-scoped `CapabilityBundle`.
4. Check that the pinned runner supports the bundle transport.
5. Start a clean engine session using the declared fingerprint.
6. Attach the bundle without changing the task prompt.
7. Deliver the task and scripted user events through the standard runner channel.
8. Record normalized agent messages, tool events, usage, latency, and errors.
9. Stop the engine and release runner-owned state.
10. Capture final external state independently, verify, and clean the tenant.

Final-state capture runs after normal completion, timeout, transport error, or engine error. A lost response can therefore be scored as externally successful while still recording a reliability failure.

## Engine driver requirements

Engine-specific drivers may use a streaming SDK, a non-interactive CLI protocol, or a hosted session API. The normalized `AgentRunner` contract remains the same.

For local CLI and SDK engines:

- prefer one long-lived session when the engine supports multi-turn streaming input;
- use piped structured I/O rather than a PTY when a machine-readable stream is available;
- pin compatible SDK and executable versions together;
- use a deterministic absolute working directory;
- verify transcript existence before resuming a prior session;
- normalize engine events at the driver boundary;
- buffer turn-boundary user input without silently merging or dropping messages;
- treat engine credentials separately from provider execution credentials;
- keep all network, process, clock, and filesystem boundaries replaceable in conformance tests.

Hosted runners must declare that their process isolation is externally managed. They remain eligible for compatibility and open-combination tracks, but enter a provider main track only when the engine version, prompt, tool surface, and hidden state can be pinned and audited.

## Capability transports

`CapabilityBundle.transport` names the mechanism exposed to the agent, such as `mcp`, `http-tools`, `stdio`, or an engine-native tool registration interface. The bundle may carry run-scoped opaque connection handles but never raw verifier or cleanup credentials.

The adapter may translate wire formats. It may not:

- rewrite the user request or system prompt;
- add task-specific tool-selection hints;
- perform planning, retries, or task execution for the agent;
- implement a missing provider feature;
- expose verifier observations or expected values.

Transport normalization should remove incidental integration differences without erasing product behavior. Discovery quality, schema quality, authorization handling, latency, retries performed by the provider, and returned errors remain part of the unit under test.

## Conformance before official use

A runner must pass a provider-independent conformance suite covering:

- fingerprint stability and version reporting;
- clean-session and workspace reset behavior;
- task delivery without prompt mutation;
- capability-bundle attachment;
- multi-turn clarification and approval events;
- timeout, interrupt, and malformed-event handling;
- telemetry normalization and secret redaction;
- proof that verifier and hidden task fields are not visible;
- teardown after setup, run, and transport failures.
