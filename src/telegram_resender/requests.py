"""Parsing and validation for user-submitted access requests."""

from __future__ import annotations

from dataclasses import dataclass

REQUIRED_FIELDS = ("building", "arrival_time", "vehicle", "license_plate")

FIELD_LABELS_RU: dict[str, str] = {
    "building": "объект/здание",
    "arrival_time": "дата и время прибытия",
    "vehicle": "автомобиль",
    "license_plate": "госномер",
    "contact": "контакт",
    "comment": "комментарий",
}

FIELD_LABELS_EN: dict[str, str] = {
    "building": "building",
    "arrival_time": "arrival date and time",
    "vehicle": "vehicle",
    "license_plate": "license plate",
    "contact": "contact",
    "comment": "comment",
}

ALIASES: dict[str, tuple[str, ...]] = {
    "building": ("объект", "здание", "объект/здание", "building"),
    "arrival_time": (
        "дата и время прибытия",
        "время прибытия",
        "дата прибытия",
        "arrival date and time",
        "arrival time",
        "arrival",
    ),
    "vehicle": ("автомобиль", "машина", "vehicle", "car"),
    "license_plate": ("госномер", "номер", "license plate", "plate"),
    "contact": ("контакт", "фио", "contact", "name"),
    "comment": ("комментарий", "comment", "notes", "note"),
}

ALIAS_TO_FIELD = {
    alias.casefold(): field for field, aliases in ALIASES.items() for alias in aliases
}


@dataclass(frozen=True, slots=True)
class ParsedRequest:
    """Normalized request fields and validation state."""

    fields: dict[str, str]
    missing_fields: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        """Whether all required request fields are present."""

        return not self.missing_fields


def parse_request(text: str) -> ParsedRequest:
    """Parse a labeled request template filled by a Telegram user."""

    fields: dict[str, str] = {}
    for raw_line in text.splitlines():
        if ":" not in raw_line:
            continue
        raw_label, raw_value = raw_line.split(":", 1)
        label = _normalize_label(raw_label)
        value = raw_value.strip()
        field = ALIAS_TO_FIELD.get(label)
        if field is not None and value:
            fields[field] = value

    missing_fields = tuple(field for field in REQUIRED_FIELDS if field not in fields)
    return ParsedRequest(fields=fields, missing_fields=missing_fields)


def format_missing_fields(missing_fields: tuple[str, ...], *, locale: str) -> str:
    """Render missing field names for user-facing validation messages."""

    labels = FIELD_LABELS_RU if locale == "ru" else FIELD_LABELS_EN
    return ", ".join(labels.get(field, field) for field in missing_fields)


def _normalize_label(label: str) -> str:
    return " ".join(label.strip().casefold().split())
