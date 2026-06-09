# Branch Protection

Repository has branch protection for `master` already configured from the project automation.

To enforce the same quality gates for `main` as well, run:

```powershell
pwsh ./scripts/setup-branch-protection.ps1 -Repository krotname/Bot-Telegram-Resender
```

Current required checks:

- `lint (3.12)`, `lint (3.13)`
- `types (3.12)`, `types (3.13)`
- `tests (3.12)`, `tests (3.13)`
- `security`
- `Analyze (python)`

And additional hardening:

- at least one approving review
- code owner review required
- code owners cannot bypass
- stale reviews are dismissed on new commits
- linear history required
- force pushes and deletions disabled
