"""Integration tests for service construction and settings wiring."""

from pathlib import Path

from telegram_resender.app import build_service
from telegram_resender.models import IncomingMessage, UserProfile
from telegram_resender.settings import Settings
from telegram_resender.messages import REQUEST_ACCEPTED_MESSAGE


def test_build_service_uses_project_files(tmp_path: Path) -> None:
    """Settings should load and inject dependencies without direct Telegram SDK calls."""

    whitelist_file = tmp_path / "whitelist.csv"
    whitelist_file.write_text("alice\n", encoding="utf-8")
    settings = Settings(
        bot_token="123:abc",
        forward_chat_id=100,
        whitelist_path=whitelist_file,
    )
    service = build_service(settings)
    decision = service.handle_text(
        IncomingMessage(
            chat_id=100,
            text="hello",
            user=UserProfile(username="alice"),
        )
    )

    assert decision.should_forward is True
    assert decision.response_text == REQUEST_ACCEPTED_MESSAGE
