# Runners

Runners hold the agent side of a provider comparison constant. A runner starts one pinned agent engine, attaches exactly one `CapabilityBundle`, delivers the task request verbatim, and records agent-side telemetry.

A conforming runner must:

- Declare a complete `RunnerFingerprint`
- Start from a clean task context and deterministic workspace
- Pin the engine, model, system prompt, and inference configuration
- Support only declared capability transports
- Enforce time, retry, call, token, and spending limits
- Capture messages, tool calls, approvals, errors, and timestamps
- Avoid provider-specific prompt or retry changes
- Never receive verifier credentials, expected outcomes, or hidden checks
- Emit telemetry only; the trusted harness constructs verifier evidence
- Separate runner failures from provider task failures

The executable contract lives in `agent_capability_benchmark/runners/base.py`. See `docs/agent-runner-protocol.md` for lifecycle, control variables, and comparison tracks.
