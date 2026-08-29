# Security Policy

## Supported versions

Security fixes are applied to the latest commit on the default branch. Older
research snapshots and tags are not maintained as production software.

## Reporting a vulnerability

Do not disclose credentials, command-injection paths, unsafe deserialization
cases, or other exploitable details in a public issue.

Use GitHub's private vulnerability reporting feature from the repository
Security tab.

Include the affected commit, reproduction steps, impact, and any proposed
mitigation. Reports will be acknowledged after they have been reviewed.

## Research-software warning

Several workflows load pickle files and execute external binaries. Only load
artifacts from trusted sources, review command paths, and run experiments in an
isolated environment.
