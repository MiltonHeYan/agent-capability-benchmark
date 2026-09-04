# Security Policy

## Reporting a vulnerability

Do not open a public issue for suspected credential exposure, authorization bypass, fixture isolation failure, verifier bypass, or another security-sensitive problem.

Until a private reporting address is published, contact the repository maintainers through the hosting platform's private security reporting feature. Include a minimal reproduction, affected commit, expected impact, and any evidence needed to reproduce the issue.

## Benchmark secrets

- Never commit provider credentials, user tokens, verifier credentials, or private fixture data.
- Use isolated test accounts with the minimum required permissions.
- Keep execution credentials separate from verifier credentials.
- Redact secrets and personal data from traces before publishing results.
- Rotate a credential immediately if it appears in an artifact or log.

## Supported versions

Before the first stable release, security fixes apply only to the latest commit on the default branch.
