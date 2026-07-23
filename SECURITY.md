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

### Git-ignored secret files

`.gitignore` keeps local credential files out of commits:

- `.env` and every `.env.*` variant (for example `.env.production`) are ignored,
  because they hold the real `TELEGRAM_RESENDER_BOT_TOKEN`.
- The placeholder templates `.env.example`, `.env.production.example`, and
  `.env.systemd.example` are re-included by negation patterns and stay tracked.
- The legacy repository-root `/config.py` is ignored. The pattern is anchored to
  the root, so a package module such as `src/telegram_resender/config.py` would
  still be tracked and scanned.

Never commit `whitelist.csv` or a populated `.env`; copy the `*.example`
templates instead and keep the filled-in copies local.

### Secret scanning in CI

The `Secret scan` workflow (`.github/workflows/gitleaks.yml`) runs gitleaks on
every push and on pull requests against the default branch, over the full git
history (`fetch-depth: 0`). Rules come from the upstream gitleaks defaults,
extended by `.gitleaks.toml`. The repository also defines an explicit Telegram
Bot API token detector because the gitleaks version used by CI does not include
one in its default ruleset.

`.gitleaksignore` contains two fingerprints for the revoked historical findings
in the repository-root `config.py`. Each exception is bound to an exact commit,
path, rule, and line. No path is globally allowlisted, so a future token in
`config.py` or any other file still fails the scan.

If the workflow reports a finding, treat the credential as compromised: revoke
and reissue it first, then clean up the source.

### Authorization uses immutable numeric user IDs

The whitelist trust boundary is expressed in immutable numeric Telegram user IDs
(`whitelist.csv`, one ID per line; `/whoami` reports a user's own ID). Populate
it with numeric IDs only.

Do not authorize by `@username`. Telegram usernames are mutable and can be
released and re-registered by a different account, so a username-based rule
silently transfers access to whoever claims the handle next. The route field
`allowed_usernames` is an additional routing filter applied after the numeric
whitelist check has already granted access; it is not an authorization
mechanism and must not be used as one.

## Supply-chain controls

- Runtime, development, bootstrap, and audit dependencies are installed from hash-locked requirement files.
- The Docker runtime base image is pinned by immutable digest.
- GitHub Actions are pinned by commit SHA.
- Release packages are published with SHA-256 checksums and GitHub artifact attestations.
