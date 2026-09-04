# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and the project intends to use semantic versioning once the task and result contracts stabilize.

## Unreleased

### Added

- Vendor-neutral repository structure and terminology.
- Benchmark principles and v0.1 evaluation specification.
- Machine-readable task schema.
- Task-validation CLI, manifest integrity checks, and semantic task-contract checks.
- Ten public v0.1 task contracts across core, authentication, governance, payment, and full-stack tracks.
- Provider adapter contract, normalized evidence schema, deterministic verifier engine, and loopback-only reference fixture session server.
- Isolated-run harness and sandbox backend contract with separate execution, verification, and cleanup credential roles.
- Separate provider `CapabilityBundle` and fixed `AgentRunner` contracts, with reproducible runner fingerprints and hidden-field isolation.
- Agent runner protocol for controlled provider comparisons, cross-engine blocks, and engine conformance.
- Project landing page, documentation map, governance, conduct, citation, and integration-proposal scaffolding.
- Test-tenant threat model covering disposable runner state, egress allowlists, run namespaces, external-state verification, cleanup, and quarantine.
- Contributor, security, pull request, issue, and CI scaffolding.
