# Branch Protection

Branch protection is applied to production branches by automation.

To apply protection manually, use:

```powershell
pwsh ./scripts/setup-branch-protection.ps1 -Repository krotname/Bot-Telegram-Resender
```

or with bash:

```bash
./scripts/setup-branch-protection.sh krotname/Bot-Telegram-Resender main master
```

### Automated workflow

The repository now has `.github/workflows/branch-protection.yml` which:

- runs on `main` / `master` pushes and weekly schedule;
- applies protection automatically when branch exists;
- skips if no `BRANCH_PROTECTION_TOKEN` is configured.

You need to create a secret in repository settings:

- `BRANCH_PROTECTION_TOKEN` with repository admin permissions (to manage branch protection rules).

### Current required checks

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
