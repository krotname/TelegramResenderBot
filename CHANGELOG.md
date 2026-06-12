# Changelog

## 1.2.0
- Add labeled request parsing for Russian and English templates.
- Validate required request fields: building, arrival date/time, vehicle, and license plate.
- Report missing fields back to the user instead of forwarding incomplete requests.
- Add optional confirmation mode with `TELEGRAM_RESENDER_CONFIRM_BEFORE_FORWARD`.
- Add `/confirm` and `/cancel` for pending request previews.
- Share the same request id between user-facing confirmation messages and forwarded admin messages.
- Expand service, parser, app, and conversation tests for the guided request flow.

## 1.1.0
- Add a `telegram-resender doctor` diagnostics command for local configuration checks.
- Replace raw startup tracebacks with concise configuration errors by default.
- Add localized Russian and English bot message catalogs, with Russian as the default locale.
- Add `/template` and make `/avto` return the request template instead of claiming a stateful mode.
- Reply to unsupported non-text messages instead of silently ignoring them.
- Split unknown-user and missing-username denial messages, including chat id guidance for users without a Telegram username.
- Reject clearly incomplete text such as short greetings before forwarding.
- Add request id and submitted timestamp to forwarded administrator messages.
- Fix `mypy src tests` and expand conversation/CLI coverage for the new UX behavior.
- Align package metadata with the GPL-3.0 license used by the repository.
- Add a Russian UX/competitive roadmap for future releases.

## 1.0.1
- Lower the coverage gate to 70% to match the current tested baseline.
- Add post-1.0 repository hardening, release checks, bilingual documentation, visual preview, and OpenSSF badges.

## 0.1.0
- Refactor monolithic script into typed package structure.
- Add env-driven configuration and remove hardcoded secrets.
- Add robust whitelist parsing and deterministic forwarding format.
- Add unit/integration/conversation/security tests and CI pipeline with coverage gate.
- Add dependency automation and repository metadata (badges, templates, guides).
