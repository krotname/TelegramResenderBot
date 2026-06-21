# Security Policy

## Supported versions

Security fixes are handled on the default branch and the latest public release line.

## Reporting vulnerabilities

Do not open a public issue for suspected vulnerabilities, bot tokens, chat IDs, secrets, or exploit details.

Report vulnerabilities through GitHub private vulnerability reporting:
https://github.com/krotname/TelegramResenderBot/security/advisories/new

Include:

- affected version or commit,
- reproduction steps,
- impact scope,
- relevant configuration with secrets redacted,
- suggested mitigation if available.

The maintainer aims to acknowledge valid reports within 48 hours and provide a remediation timeline after the impact is confirmed.

## Secure configuration

- Secrets are read from environment variables.
- Tokens and credentials must not be stored in source files.
- Startup validation blocks obvious placeholder credentials.

## Supply-chain controls

- Runtime, development, bootstrap, and audit dependencies are installed from hash-locked requirement files.
- The Docker runtime base image is pinned by immutable digest.
- GitHub Actions are pinned by commit SHA.
- Release packages are published with SHA-256 checksums and GitHub artifact attestations.
