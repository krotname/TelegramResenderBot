# Architecture

```text
User Telegram Message -> app.incoming_from_message -> service.ResenderService.handle_text ->
  [whitelist.check + template parsing + required-field validation] ->
    - missing sender ID: bot replies with chat-id guidance
    - unknown user ID: bot replies with private-bot denial
    - incomplete request: bot replies with missing-field guidance
    - no route matched: bot replies without forwarding
    - allowed: formatter.MessageFormatter.format_forward -> delivery log -> matching target chats
    - confirmation mode: successful preview -> SQLite pending state with TTL/version ownership ->
      /confirm [request-id] -> atomic claim -> current-whitelist recheck -> target chat,
      or /cancel [request-id]; pending state survives process restarts
```

- `settings.Settings`: validates runtime environment and normalizes paths.
- `whitelist.Whitelist`: file-backed access control.
- `service.ResenderService`: pure decision function.
- `requests.py`: request-template parsing and required-field validation.
- `routes.py`: strict duplicate-safe JSON route loading, numeric-ID authorization filters,
  and legacy non-security username route labels.
- `formatting.MessageFormatter`: stable forwarding format.
- `delivery.py`: retry/backoff wrapper for Telegram send failures.
- `storage.py`: SQLite delivery log, owner/version leases, persistent pending previews,
  schema migration/validation, and CSV export.
- `telegram_limits.py`: shared Telegram UTF-16 message-length rules.
- `app.py`: adapter layer to aiogram (`Message` -> domain model).
- `messages.py`: localized user-facing message catalogs.
- `cli.py`: explicit application entrypoint, `doctor`, `health`, and CSV export commands.
- `src/telegram_resender/__main__.py`: module entry point for `python -m telegram_resender`.

Admin command flow:

```text
/whoami -> reports Telegram user id and chat id
/admin_status, /whitelist_count, /reload_whitelist ->
  app._is_admin checks TELEGRAM_RESENDER_ADMIN_IDS ->
    denied: localized admin access denial
    allowed: service status or service.reload_whitelist(settings.whitelist_path)
```

Delivery flow:

```text
matched route target -> storage.RequestLog.begin_delivery ->
  already delivered or actively leased: skip duplicate send
  atomic owner/version lease: delivery.send_with_retry -> owner-checked delivered/failed state
  stale lease: a newer version may reclaim ownership after the configured timeout
health/doctor -> verify delivery, lease, pending, and sequence table schemas
```

Deployment surface:

- `Dockerfile`: container runtime using `/data` for whitelist and SQLite storage.
- `docker-compose.yml`: local production-style compose service.
- `deploy/telegram-resender.service`: systemd unit example.
- `TELEGRAM_RESENDER_LOG_FORMAT=JSON`: structured logs for production collectors.
- `telegram-resender health`: concise process-manager health check.

## Design goals

- Keep bot logic decoupled from Telegram SDK where possible.
- Keep behavior deterministic.
- Keep secrets in environment only.
- Keep startup failures explicit and early.
