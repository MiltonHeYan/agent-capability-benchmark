# Governance

Agent Capability Benchmark is an open, vendor-neutral project. Governance exists to protect methodological credibility while making it straightforward for sustained contributors to become maintainers.

## Roles

### Contributors

Anyone who opens an issue, reviews a proposal, improves documentation, submits a task, or contributes code is a contributor.

### Reviewers

Reviewers have demonstrated sound judgment in at least one area such as task design, verifiers, runners, adapters, sandboxing, statistics, security, or documentation. They may triage issues and review changes in that area.

### Maintainers

Maintainers merge changes, manage releases, steward the roadmap, and uphold neutrality and reproducibility. Maintainer access is offered to reviewers who contribute consistently, collaborate constructively, and show judgment across multiple changes. Existing maintainers document the decision publicly.

## Decision process

- Routine fixes and additive tasks use normal pull-request review.
- Changes to scoring, eligibility, schemas, hidden-task policy, or historical comparability begin with a public design discussion.
- Decisions prefer evidence and rough consensus over voting.
- Material methodology decisions are recorded in versioned documentation before release.
- Until the project has two active maintainers, the repository owner may merge after public review. Once two or more maintainers are active, methodology changes require approval from two maintainers.

## Neutrality and conflicts

Affiliation with a capability provider does not prevent contribution. Contributors must disclose a material affiliation when proposing or reviewing provider-specific adapters or published results.

A contributor may implement an adapter for an affiliated provider, but may not be the sole approver of that provider's official result. Public tasks, scoring rules, and core documentation must not privilege a provider-specific interface.

## Releases and comparability

Maintainers version tasks, fixtures, schemas, runners, adapters, verifiers, and scoring logic. A release note must identify changes that break or weaken comparison with earlier results. Official results pin exact commits and runner fingerprints.

## Conduct and security

Participation follows [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Security-sensitive reports follow [SECURITY.md](SECURITY.md) and must not be posted publicly.
