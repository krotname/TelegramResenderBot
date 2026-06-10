# Testing Strategy

## Unit
`tests/unit/*` covers normalization, formatting, and forwarding decisions.

## Integration
`tests/integration/*` covers service construction and cross-module wiring.

## Conversation
`tests/conversation/*` validates user-visible message flow paths at domain level.

## Security
`tests/security/*` validates startup token validation and configuration guards.

## CI Gate
GitHub Actions pipeline runs:

- Ruff (`check`, `format`)
- Mypy (strict mode)
- Pytest with branch coverage (`--cov-fail-under=70`)
- Pip audit on lockless dependency set in env
- CodeQL and dependency review
- OpenSSF Scorecard via GitHub Actions, with SARIF upload to GitHub code scanning and
  `publish_results: true` for the public Scorecard API badge

## Adding tests
1. Add a failing test first.
2. Implement the smallest change.
3. Keep tests deterministic and avoid network I/O.
4. Update expected behavior in README if visible output changes.
