"""Integration tests for service construction and settings wiring."""

from pathlib import Path

from telegram_resender.app import build_service
from telegram_resender.messages import REQUEST_ACCEPTED_MESSAGE
from telegram_resender.models import IncomingMessage, UserProfile
from telegram_resender.settings import Settings

VALID_REQUEST = (
    "Объект/здание: Башня А\n"
    "Дата и время прибытия: 12.06.2026 10:30\n"
    "Автомобиль: Ford Focus\n"
    "Госномер: А123ВС"
)
VALID_BOT_TOKEN = f"123456789:{'A' * 35}"


def test_build_service_uses_project_files(tmp_path: Path) -> None:
    """Settings should load and inject dependencies without direct Telegram SDK calls."""

    whitelist_file = tmp_path / "whitelist.csv"
    whitelist_file.write_text("10\n", encoding="utf-8")
    settings = Settings(
        bot_token=VALID_BOT_TOKEN,
        forward_chat_id=100,
        whitelist_path=whitelist_file,
    )
    service = build_service(settings)
    decision = service.handle_text(
        IncomingMessage(
            chat_id=100,
            text=VALID_REQUEST,
            user=UserProfile(id=10, username="alice"),
        )
    )

    assert decision.should_forward is True
    assert decision.response_text == REQUEST_ACCEPTED_MESSAGE
    assert len(decision.request_id_aliases) == 1
    assert decision.request_id_aliases[0].startswith("local-")
    assert decision.request_id_aliases[0] != decision.request_id


def test_systemd_environment_paths_match_service_layout() -> None:
    """The copyable systemd env must use the writable /opt data directory."""

    root = Path(__file__).parents[2]
    systemd_env = (root / ".env.systemd.example").read_text(encoding="utf-8")
    service = (root / "deploy" / "telegram-resender.service").read_text(encoding="utf-8")

    assert "TELEGRAM_RESENDER_WHITELIST_PATH=/opt/telegram-resender/data/" in systemd_env
    assert "TELEGRAM_RESENDER_STORAGE_PATH=/opt/telegram-resender/data/" in systemd_env
    assert "EnvironmentFile=/opt/telegram-resender/.env.production" in service
    assert "ReadWritePaths=/opt/telegram-resender/data" in service
    assert "TELEGRAM_RESENDER_WHITELIST_PATH=/data/" not in systemd_env
