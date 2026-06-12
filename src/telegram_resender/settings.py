"""Application settings loaded from environment variables."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from telegram_resender.messages import Locale, MessageCatalog, message_catalog


class Settings(BaseSettings):
    """Runtime settings with explicit validation for safe startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TELEGRAM_RESENDER_",
        extra="ignore",
        populate_by_name=True,
    )

    bot_token: str = Field(
        ...,
        description="Telegram Bot API token.",
        validation_alias=AliasChoices("TELEGRAM_RESENDER_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"),
    )
    forward_chat_id: int = Field(
        ...,
        description="Target chat or group id where accepted requests are forwarded.",
        validation_alias=AliasChoices("TELEGRAM_RESENDER_FORWARD_CHAT_ID", "FORWARD_CHAT_ID"),
    )
    whitelist_path: Path = Field(
        default=Path("whitelist.csv"),
        description="CSV file with allowed Telegram usernames.",
        validation_alias=AliasChoices("TELEGRAM_RESENDER_WHITELIST_PATH", "WHITELIST_PATH"),
    )
    polling_timeout: int = Field(default=30, ge=1, le=120)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    locale: Locale = "ru"
    confirm_before_forward: bool = False
    request_accepted_message: str | None = None
    access_denied_message: str | None = None

    @property
    def messages(self) -> MessageCatalog:
        """Localized bot messages with backward-compatible env overrides applied."""

        return message_catalog(self.locale).with_overrides(
            request_accepted=self.request_accepted_message,
            access_denied_unknown=self.access_denied_message,
        )

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, value: str) -> str:
        """Reject placeholder tokens before the application can start."""

        token = value.strip()
        placeholders = {"*****", "changeme", "change-me", "your-token", "your_bot_token"}
        if not token or token.lower() in placeholders or set(token) == {"*"}:
            msg = "bot_token must be a real Telegram Bot API token, not a placeholder"
            raise ValueError(msg)
        if ":" not in token:
            msg = "bot_token must look like a Telegram Bot API token and contain ':'"
            raise ValueError(msg)
        return token

    @field_validator("whitelist_path")
    @classmethod
    def normalize_whitelist_path(cls, value: Path) -> Path:
        """Normalize path tokens while keeping relative paths stable."""

        return value.expanduser()
