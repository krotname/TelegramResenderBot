# Contributing

Thank you for improving Telegram Resender.

## Getting started

1. Fork or create a branch from `main` (or `master` for legacy compatibility).
2. Create a focused commit with tests.
3. Run:

```bash
python -m pip install -e .[dev]
ruff check src tests
ruff format --check src tests
mypy src
pytest
```

4. Open a pull request with a short summary and test output.

## Branch and commit conventions

- Use clear imperative commit titles.
- Keep each PR scoped.
- Add/adjust tests for any behavior change.
- Keep secrets and `whitelist.csv` entries out of commits.

## Review criteria

- New code has validation/tests.
- Message-processing logic remains deterministic.
- Any dependency changes include compatibility reasoning.
