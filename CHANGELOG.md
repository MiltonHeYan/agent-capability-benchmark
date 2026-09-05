# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and the project intends to use semantic versioning once the task and result contracts stabilize.

## Unreleased

### Added

- Vendor-neutral repository structure and terminology.
- Benchmark principles and v0.1 evaluation specification.
- Machine-readable task schema.
- Task-validation CLI, manifest integrity checks, and semantic task-contract checks.
- Twelve public v0.1 task contracts across core, authentication, identity, governance, payment, and full-stack tracks, including principal-preserving credential recovery and fail-closed identity-conflict cases contributed through community feedback.
- Provider adapter contract, normalized evidence schema, deterministic verifier engine, and loopback-only reference fixture session server.
- Isolated-run harness and sandbox backend contract with separate execution, verification, and cleanup credential roles.
- Separate provider `CapabilityBundle` and fixed `AgentRunner` contracts, with reproducible runner fingerprints and hidden-field isolation.
- Agent runner protocol for controlled provider comparisons, cross-engine blocks, and engine conformance.
- JSONL subprocess runner with scripted user events, stable driver identity, structured failures,
  secret redaction, timeout enforcement, and deterministic offline conformance fixtures.
- Project landing page, documentation map, governance, conduct, citation, and integration-proposal scaffolding.
- Current GitHub Actions runtimes without Node.js 20 deprecation warnings.
- Test-tenant threat model covering disposable runner state, egress allowlists, run namespaces, external-state verification, cleanup, and quarantine.
- Contributor, security, pull request, issue, and CI scaffolding.
