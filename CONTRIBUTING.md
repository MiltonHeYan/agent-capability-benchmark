# Contributing

Thank you for helping improve the benchmark. Contributions should increase reproducibility, neutrality, or the quality of independently verified task outcomes.

## Development setup

Requirements: Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pre-commit install
make check
```

## Contribution types

- Task contracts and deterministic verifiers
- Provider adapters that preserve task neutrality
- Runner and trace normalization improvements
- Scoring and statistical methodology
- Documentation, CI, and reproducibility fixes

Large architecture changes and scoring changes should begin with a design discussion. Small fixes can go directly to a pull request.

Contributors interested in ongoing stewardship should also read [GOVERNANCE.md](GOVERNANCE.md). Maintainer access is earned through sustained contribution and sound review judgment, not employment or provider affiliation.

## Adding a task

Public tasks live under `tasks/public/<track>/` and must validate against `spec/task.schema.json`.

Every task must include:

- A natural-language request that does not reveal a provider-specific solution
- Explicit track eligibility and required capabilities
- A resettable fixture
- Approval, prohibited-action, and data-boundary rules
- Time, retry, call, and optional spending limits
- An independent verifier and observable success condition

Run:

```bash
capability-bench validate tasks/public
```

Task authors must not add provider names, provider-specific tool identifiers, or task-specific adapter hints to core task files. Provider details belong in adapter manifests and result metadata.

## Tests

Bug fixes require a regression test. Schema or scoring changes require tests for both accepted and rejected inputs. New tasks require at least one verifier contract test before they become leaderboard-eligible.

```bash
make check
```

## Commit style

Use a short imperative subject, no longer than 72 characters:

```text
type: concise description
```

Accepted types include `feat`, `fix`, `docs`, `test`, `chore`, and `refactor`.

## Pull requests

Describe the motivation, material changes, validation performed, and any effect on historical comparability. Fill in the repository pull request template.
