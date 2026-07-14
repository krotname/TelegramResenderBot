# Changelog

## 1.6.2
- Harden storage, message handling, dependency locks, Docker metadata, and CI/release checks after repository audit.
- Add atomic versioned SQLite delivery leases with stale-owner recovery.
- Persist confirmation previews and ownership versions in SQLite across process restarts.
- Add immutable `allowed_user_ids` route filters while retaining username filters for migration.
- Reject duplicate route JSON keys and normalized-empty username filters.
- Add bounded retry guidance after failed confirmed delivery.
- Split Docker and systemd environment templates so their data paths match each runtime.

## 1.6.1
- Apply `ruff format` to match the CI formatter gate after the `1.6.0` release.
- No functional changes.

## 1.6.0
- Add Dockerfile and docker-compose deployment templates.
- Add systemd unit example and `.env.production.example`.
- Add structured logging with `TELEGRAM_RESENDER_LOG_FORMAT=TEXT|JSON`.
- Add `telegram-resender health` for process-manager health checks.
- Document Docker, systemd, health checks, and known limitations.

## 1.5.0
- Add SQLite delivery log via `TELEGRAM_RESENDER_STORAGE_PATH`.
- Add idempotent delivery per request id and target chat.
- Add retry/backoff for transient Telegram API send failures.
- Persist delivery states as `pending`, `delivered`, or `failed` with last error text.
- Add `telegram-resender doctor --storage-check`.
- Add `telegram-resender export-requests --since YYYY-MM-DD` CSV export.
- Add delivery, storage, CLI export, and idempotent app tests.

## 1.4.0
- Add optional JSON route configuration via `TELEGRAM_RESENDER_ROUTES_PATH`.
- Support multiple forwarding routes with `name`, `target_chat_id`, `allowed_usernames`, `keywords_any`, `keywords_none`, `template`, and `enabled`.
- Preserve backward compatibility with `TELEGRAM_RESENDER_FORWARD_CHAT_ID` when no routes file is configured.
- Forward one request to every matching route destination.
- Add route-specific templates with `{route}` and `{request}` placeholders.
- Validate routes in `telegram-resender doctor` and report route count.
- Add `routes.example.json` and tests for route parsing, filtering, and multi-route forwarding.

## 1.3.0
- Add `TELEGRAM_RESENDER_ADMIN_IDS` for Telegram user IDs allowed to run admin operations.
- Add `/whoami` so users can discover their Telegram user id and chat id.
- Add admin-only `/admin_status`, `/whitelist_count`, and `/reload_whitelist` commands.
- Support runtime whitelist reload without restarting the bot process.
- Add admin access-denied responses and audit logging for whitelist reload attempts.
- Include admin user count in `telegram-resender doctor`.
- Expand tests for admin authorization, runtime reload, and admin id parsing.

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
