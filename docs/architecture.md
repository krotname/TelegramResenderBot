# Architecture

```text
User Telegram Message -> app.incoming_from_message -> service.ResenderService.handle_text ->
  [whitelist.check + request sanity check] ->
    - missing username: bot replies with chat-id guidance
    - unknown username: bot replies with private-bot denial
    - incomplete request: bot replies with request template guidance
    - allowed: formatter.MessageFormatter.format_forward -> target chat
```

- `settings.Settings`: validates runtime environment and normalizes paths.
- `whitelist.Whitelist`: file-backed access control.
- `service.ResenderService`: pure decision function.
- `formatting.MessageFormatter`: stable forwarding format.
- `app.py`: adapter layer to aiogram (`Message` -> domain model).
- `messages.py`: localized user-facing message catalogs.
- `cli.py`: explicit application entrypoint and `doctor` diagnostics.
- `src/telegram_resender/__main__.py`: module entry point for `python -m telegram_resender`.

## Design goals

- Keep bot logic decoupled from Telegram SDK where possible.
- Keep behavior deterministic.
- Keep secrets in environment only.
- Keep startup failures explicit and early.
