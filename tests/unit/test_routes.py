"""Unit tests for route config parsing and matching."""

from pathlib import Path

import pytest

from telegram_resender.routes import load_routes


def test_load_routes_parses_json_config(tmp_path: Path) -> None:
    """Routes should support usernames, keyword filters and templates."""

    path = tmp_path / "routes.json"
    path.write_text(
        """
        {
          "routes": [
            {
              "name": "gate",
              "target_chat_id": 100,
              "allowed_usernames": ["@Alice"],
              "keywords_any": ["tower"],
              "keywords_none": ["cancel"],
              "template": "[{route}]\\n{request}"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    routes = load_routes(path)

    assert len(routes) == 1
    assert routes[0].matches(username="alice", text="Tower A request") is True
    assert routes[0].matches(username="bob", text="Tower A request") is False
    assert routes[0].matches(username="alice", text="Tower A cancel") is False
    assert routes[0].render_forward_text("payload") == "[gate]\npayload"


def test_load_routes_rejects_empty_config(tmp_path: Path) -> None:
    """Invalid routes config should fail early in doctor/startup."""

    path = tmp_path / "routes.json"
    path.write_text('{"routes": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="at least one route"):
        load_routes(path)
