"""Unit tests for whitelist normalization and loading."""

from pathlib import Path

import pytest

from telegram_resender.whitelist import Whitelist, normalize_username, parse_user_id


def test_normalize_username_handles_variants() -> None:
    """Verify that whitespace, leading @ and case do not affect matching."""

    assert normalize_username("  @UserName ") == "username"
    assert normalize_username("Second") == "second"
    assert normalize_username(None) is None
    assert normalize_username("   ") is None


def test_whitelist_loads_csv_and_normalizes(tmp_path: Path) -> None:
    """Ensure first-column parsing and comment support are preserved."""

    file_path = tmp_path / "whitelist.csv"
    file_path.write_text("10\n20\n# ignored\n30, extra\n", encoding="utf-8")
    whitelist = Whitelist.from_file(file_path)

    assert whitelist.contains(10)
    assert whitelist.contains("20")
    assert whitelist.contains(30)
    assert not whitelist.contains(40)


def test_whitelist_missing_file_raises_error() -> None:
    """Missing whitelist file should fail early with FileNotFoundError."""

    with pytest.raises(FileNotFoundError):
        Whitelist.from_file(Path("missing.csv"))


def test_parse_user_id_rejects_usernames() -> None:
    """Usernames must not be accepted as authorization identifiers."""

    assert parse_user_id(" 123 ") == 123
    with pytest.raises(ValueError):
        parse_user_id("alice")


@pytest.mark.parametrize("value", [0, -1, True, "-100"])
def test_parse_user_id_rejects_non_positive_values(value: int | str) -> None:
    """Telegram sender user IDs are positive integers, never chat IDs or booleans."""

    with pytest.raises(ValueError, match="positive integer"):
        parse_user_id(value)
