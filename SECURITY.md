# Security policy

## Scope

This is research software. The software version is `0.2.0rc1`; no production support period or response-time guarantee is offered. A local regression pass and a secret scan do not constitute a security certification.

Studio binds to `127.0.0.1`. Any proxy, network exposure or access-control configuration is outside the default package and must be assessed by the operator.

## Report a vulnerability privately

If private vulnerability reporting is enabled on the repository, use **Security → Report a vulnerability**. Otherwise contact a maintainer using the contact details in [CITATION.cff](CITATION.cff). These are the project's existing contacts; this document does not designate an institutional security-response team.

Include the affected version, operating system, Python/dependency versions, a minimal reproduction and the expected impact. Omit live credentials, personal information and restricted datasets or model files. Do not post exploit details, credentials or restricted artifacts in a public issue while a report is being assessed.

Maintainers will assess the report, request clarification where needed and coordinate any fix and disclosure. Avoid publicly disclosing another person's report or data without permission. Release or institutional approval requirements remain separate from this reporting process.

## Dependency and artifact handling

The default environment is CPU-only. Optional paper/render tools and any external artifacts have separate scopes. The artifact installer checks declared file identities; it does not grant redistribution rights or prove that arbitrary files are safe.

The secret-scan workflow scans repository history using a pinned Gitleaks binary with redacted output. Its configuration inherits upstream detectors and excepts only nine reviewed public CACTI/source SHA-256 values. These are exact-value exceptions, not directory, field-name or general hexadecimal exclusions. A fresh synthetic non-live API key is still detected by the configured scanner. Review new findings individually rather than broadening the exceptions indiscriminately. Dependency inventory and license information are recorded in the release SBOM and third-party notices. Keep package and artifact permissions under review before publishing.
