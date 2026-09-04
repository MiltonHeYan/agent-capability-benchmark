# Agent Capability Benchmark

A vendor-neutral, reproducible benchmark for infrastructure that supplies external capabilities to AI agents.

The benchmark keeps the model, agent runtime, task prompt, fixtures, and evaluation rules fixed. It varies only the capability provider and its adapter. This isolates how much the capability layer contributes to real-world task completion.

## Status

Pre-alpha. The repository defines the benchmark principles, v0.1 evaluation model, task schema, adapter boundary, and a small validation CLI. A reference runner will follow after the task contract is validated.

## Quick start

Requirements: Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
make check
```

Validate the public task set directly:

```bash
capability-bench validate tasks/public
```

## What is measured

The core track evaluates the complete path from intent to verified external outcome:

1. Discover an appropriate capability.
2. Inspect its inputs, constraints, permissions, and price.
3. Connect the required user account or credential.
4. Execute the action.
5. Verify the resulting external state.
6. Recover from expected failures.
7. Respect approval and policy boundaries.
8. Report latency, calls, and cost.

Optional tracks cover authentication, memory, payments, governance, identity, and sandboxed execution. Products enter only the tracks for which they meet the published eligibility requirements.

## What is not measured

- General model intelligence
- Prompt-writing quality
- Self-reported feature or integration counts
- A single opaque leaderboard score
- Capabilities that cannot be independently verified

## Repository layout

```text
adapters/                    Provider integration boundary and manifests
agent_capability_benchmark/  Validation CLI and benchmark package
docs/                        Principles and versioned specifications
runners/                     Agent hosts held constant across comparisons
spec/                        Machine-readable schemas
tasks/public/                Public benchmark task definitions
tests/                       Contract and CLI tests
verifiers/                   Independent outcome verification contracts
```

## Core vocabulary

- **Provider**: the capability infrastructure under evaluation.
- **Adapter**: the smallest integration needed to expose a provider to the runner.
- **Runner**: the fixed agent host used to execute a task.
- **Task**: a versioned goal, fixture, policy, and evaluation contract.
- **Verifier**: an independent check of the final external state.
- **Run**: one attempt by one provider configuration on one task version.

## Design rule

An agent saying that an action succeeded is never sufficient evidence. A successful run requires an independent verifier to observe the expected state.

See [the v0.1 specification](docs/benchmark-v0.1.md), [public task catalog](docs/task-catalog-v0.1.md), [benchmark principles](docs/principles.md), and [contribution guide](CONTRIBUTING.md).

## Project policy

The repository is vendor-neutral. Core documentation and public task contracts use generic provider identifiers. Provider-specific implementations and results must remain isolated in adapters or result metadata.

## License

Released under the [MIT License](LICENSE).
