"""Unit tests for route config parsing and matching."""

import json
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
              "allowed_user_ids": [10],
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
    assert routes[0].matches(user_id=10, username="alice", text="Tower A request") is True
    assert routes[0].matches(user_id=20, username="alice", text="Tower A request") is False
    assert routes[0].matches(user_id=10, username="bob", text="Tower A request") is False
    assert routes[0].matches(user_id=10, username="alice", text="Tower A cancel") is False
    assert routes[0].render_forward_text("payload") == "[gate]\npayload"


def test_load_routes_rejects_empty_config(tmp_path: Path) -> None:
    """Invalid routes config should fail early in doctor/startup."""

    path = tmp_path / "routes.json"
    path.write_text('{"routes": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="at least one route"):
        load_routes(path)


def test_load_routes_rejects_invalid_template_at_startup(tmp_path: Path) -> None:
    """Unknown template fields should fail validation before handling user messages."""

    path = tmp_path / "routes.json"
    path.write_text(
        '{"routes": [{"name": "gate", "target_chat_id": 100, "template": "{missing}"}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid template"):
        load_routes(path)


@pytest.mark.parametrize("template", ["   ", "x" * 4097])
def test_load_routes_rejects_unsendable_template(tmp_path: Path, template: str) -> None:
    """A route template that cannot produce a Telegram message should fail at startup."""

    path = tmp_path / "routes.json"
    path.write_text(
        json.dumps({"routes": [{"name": "gate", "target_chat_id": 100, "template": template}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="template"):
        load_routes(path)


@pytest.mark.parametrize(
    ("route_fragment", "error"),
    [
        ('"enabled": "false"', "enabled must be a boolean"),
        ('"target_chat_id": 1.5', "target_chat_id must be a non-zero integer"),
        ('"keywords_any": 42', "keyword filters must be"),
    ],
)
def test_load_routes_rejects_mistyped_fields(
    tmp_path: Path,
    route_fragment: str,
    error: str,
) -> None:
    """Mistyped JSON values must not be silently coerced into unsafe routes."""

    path = tmp_path / "routes.json"
    base = '"name": "gate", "target_chat_id": 100'
    if route_fragment.startswith('"target_chat_id"'):
        base = '"name": "gate"'
    path.write_text(f'{{"routes": [{{{base}, {route_fragment}}}]}}', encoding="utf-8")

    with pytest.raises(ValueError, match=error):
        load_routes(path)


@pytest.mark.parametrize(
    "unknown_field",
    ["allowed_username", "enable", "keyword_any"],
)
def test_load_routes_rejects_unknown_route_fields_fail_closed(
    tmp_path: Path,
    unknown_field: str,
) -> None:
    """A route typo must not silently remove an access or keyword restriction."""

    path = tmp_path / "routes.json"
    path.write_text(
        f'{{"routes": [{{"name": "gate", "target_chat_id": 100, "{unknown_field}": []}}]}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=rf"unknown field.*{unknown_field}"):
        load_routes(path)


def test_load_routes_rejects_unknown_document_fields(tmp_path: Path) -> None:
    """The wrapper object should use a closed schema as well."""

    path = tmp_path / "routes.json"
    path.write_text('{"route": []}', encoding="utf-8")

    with pytest.raises(ValueError, match=r"unknown field.*'route'"):
        load_routes(path)


@pytest.mark.parametrize("field_name", ["allowed_usernames", "keywords_any", "keywords_none"])
def test_load_routes_rejects_blank_filter_values(tmp_path: Path, field_name: str) -> None:
    """Blank filters must not normalize into an unrestricted route."""

    path = tmp_path / "routes.json"
    path.write_text(
        f'{{"routes": [{{"name": "gate", "target_chat_id": 100, "{field_name}": [""]}}]}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non-empty strings"):
        load_routes(path)


def test_load_routes_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    """Duplicate keys must not redirect a route or erase an authorization filter."""

    path = tmp_path / "routes.json"
    path.write_text(
        """
        {
          "routes": [{
            "name": "private",
            "target_chat_id": -100,
            "target_chat_id": -999,
            "allowed_user_ids": [10],
            "allowed_user_ids": []
          }]
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"duplicate JSON key 'target_chat_id'"):
        load_routes(path)


def test_load_routes_rejects_username_that_normalizes_empty(tmp_path: Path) -> None:
    """A placeholder '@' must not silently turn a restricted route into an open route."""

    path = tmp_path / "routes.json"
    path.write_text(
        '{"routes": [{"target_chat_id": 100, "allowed_usernames": [" @ "]}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="valid non-empty usernames"):
        load_routes(path)


@pytest.mark.parametrize("value", [0, -1, True, "not-an-id", 1.5])
def test_load_routes_rejects_invalid_allowed_user_ids(tmp_path: Path, value: object) -> None:
    """Numeric route authorization must fail closed for malformed IDs."""

    path = tmp_path / "routes.json"
    path.write_text(
        json.dumps({"routes": [{"target_chat_id": 100, "allowed_user_ids": [value]}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="allowed_user_ids"):
        load_routes(path)


def test_legacy_username_only_route_remains_compatible(tmp_path: Path) -> None:
    """Existing routes keep their legacy username routing behavior during migration."""

    path = tmp_path / "routes.json"
    path.write_text(
        '{"routes": [{"target_chat_id": 100, "allowed_usernames": ["alice"]}]}',
        encoding="utf-8",
    )

    route = load_routes(path)[0]
    assert route.allowed_user_ids == frozenset()
    assert route.matches(user_id=999, username="alice", text="request") is True
