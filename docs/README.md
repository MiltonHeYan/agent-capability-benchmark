# Documentation

Use this map to find the right level of detail without reading the repository front to back.

| Document | Read it when you need to understand |
|---|---|
| [Benchmark specification v0.1](benchmark-v0.1.md) | Unit under test, tracks, verdicts, metrics, and publication protocol |
| [Benchmark principles](principles.md) | Non-negotiable neutrality, reproducibility, and evidence rules |
| [Public task catalog](task-catalog-v0.1.md) | Initial task families and their intended coverage |
| [Agent runner protocol](agent-runner-protocol.md) | Fixed-agent control variables and engine integration |
| [JSONL subprocess runner](jsonl-subprocess-runner.md) | CLI engine wire protocol, lifecycle, and security boundaries |
| [Sandbox and test-tenancy](sandbox-and-tenancy.md) | Credentials, external accounts, cleanup, and trust boundaries |
| [Reference runtime](reference-runtime.md) | Executable contracts, evidence format, fixture server, and verifier |

Implementation-facing contracts also live in:

- [`spec/task.schema.json`](../spec/task.schema.json)
- [`spec/evidence.schema.json`](../spec/evidence.schema.json)
- [`adapters/README.md`](../adapters/README.md)
- [`runners/README.md`](../runners/README.md)
- [`verifiers/README.md`](../verifiers/README.md)
