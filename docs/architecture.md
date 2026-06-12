# Architecture

```text
User Telegram Message -> app.incoming_from_message -> service.ResenderService.handle_text ->
  [whitelist.check + template parsing + required-field validation] ->
    - missing username: bot replies with chat-id guidance
    - unknown username: bot replies with private-bot denial
    - incomplete request: bot replies with missing-field guidance
    - allowed: formatter.MessageFormatter.format_forward -> target chat
    - confirmation mode: preview -> /confirm -> target chat, or /cancel
```

- `settings.Settings`: validates runtime environment and normalizes paths.
- `whitelist.Whitelist`: file-backed access control.
- `service.ResenderService`: pure decision function.
- `requests.py`: request-template parsing and required-field validation.
- `formatting.MessageFormatter`: stable forwarding format.
- `app.py`: adapter layer to aiogram (`Message` -> domain model).
- `messages.py`: localized user-facing message catalogs.
- `cli.py`: explicit application entrypoint and `doctor` diagnostics.
- `src/telegram_resender/__main__.py`: module entry point for `python -m telegram_resender`.

Admin command flow:

```text
/whoami -> reports Telegram user id and chat id
/admin_status, /whitelist_count, /reload_whitelist ->
  app._is_admin checks TELEGRAM_RESENDER_ADMIN_IDS ->
    denied: localized admin access denial
    allowed: service status or service.reload_whitelist(settings.whitelist_path)
```

## Design goals

- Keep bot logic decoupled from Telegram SDK where possible.
- Keep behavior deterministic.
- Keep secrets in environment only.
- Keep startup failures explicit and early.
