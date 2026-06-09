# Architecture

```text
User Telegram Message -> app.incoming_from_message -> service.ResenderService.handle_text ->
  [whitelist.check] ->
    - denied: bot replies with denied message
    - allowed: formatter.MessageFormatter.format_forward -> target chat
```

- `settings.Settings`: validates runtime environment and normalizes paths.
- `whitelist.Whitelist`: file-backed access control.
- `service.ResenderService`: pure decision function.
- `formatting.MessageFormatter`: stable forwarding format.
- `app.py`: adapter layer to aiogram (`Message` -> domain model).
- `cli.py`: explicit application entrypoint.
- `src/telegram_resender/__main__.py`: module entry point for `python -m telegram_resender`.

## Design goals

- Keep bot logic decoupled from Telegram SDK where possible.
- Keep behavior deterministic.
- Keep secrets in environment only.
- Keep startup failures explicit and early.
