# Dependency Policy

This repository treats runtime dependencies, developer tools, Docker runtime, and
GitHub Actions as supply-chain inputs.

## Python Dependencies

- `requirements.lock` pins runtime dependencies with hashes.
- `requirements-dev.lock` pins test, lint, type-check, and build tooling with hashes.
- `requirements-bootstrap.lock` pins bootstrap tooling used before installing the other locks.
- `requirements-audit.lock` pins audit tooling used by CI security checks.

CI and Docker installs use `pip install --require-hashes` so an unpinned or
unexpected package version fails the build.

## Docker Runtime

The Docker base image is pinned by digest in `Dockerfile`. Update it only through
a reviewed dependency-maintenance change that rebuilds and retests the image.

## GitHub Actions

Workflow actions are pinned by immutable commit SHA with the original tag kept in
a comment for readability. Dependabot groups workflow updates so each change can
be reviewed as a supply-chain update.

## Releases

The release workflow builds the wheel and source distribution from a clean tree,
publishes `SHA256SUMS.txt`, and creates GitHub artifact attestations for package
provenance. Release assets should be verified before deployment:

```bash
sha256sum -c SHA256SUMS.txt
gh attestation verify telegram_resender-*.whl --repo krotname/TelegramResenderBot
```
