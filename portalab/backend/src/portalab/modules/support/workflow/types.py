"""Ticket types and their custom fields (T018; R4): a closed field schema (``text``, ``long_text``,
``select``, ``multi_select``, ``number``, ``boolean``, ``date``, ``user``, and ``rating`` — 1 to 5 stars,
027), required fields enforced at creation **naming** what is missing (``ticket.required_fields_missing``),
and per-field privacy (``private`` = requester and staff only… or ``staff_only``). Feedback forms reuse the
same field schema."""

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from portalab.core.errors import ValidationFailed

FieldType = Literal[
    "text", "long_text", "select", "multi_select", "number", "boolean", "date", "user", "rating"
]


class FieldDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    label: str = Field(min_length=1, max_length=120)
    type: FieldType
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=50)
    visibility: Literal["requester_and_staff", "staff_only"] = "requester_and_staff"
    max_length: int = Field(default=2000, ge=1, le=20000)


class FieldsInvalid(ValidationFailed):
    default_code = "ticket.fields_invalid"
    default_title = "Some fields are not valid"


class RequiredFieldsMissing(ValidationFailed):
    default_code = "ticket.required_fields_missing"
    default_title = "Required fields are missing"


def parse_fields(raw: Sequence[Mapping[str, Any]]) -> list[FieldDef]:
    try:
        defs = [FieldDef.model_validate(dict(item)) for item in raw]
    except ValidationError as exc:
        raise FieldsInvalid("The field definitions are not valid.") from exc
    keys = [d.key for d in defs]
    if len(keys) != len(set(keys)):
        raise FieldsInvalid("Field keys must be unique.")
    for definition in defs:
        if definition.type in ("select", "multi_select") and not definition.options:
            raise FieldsInvalid(f"Field {definition.key} needs options.")
    return defs


def _coerce(definition: FieldDef, value: Any) -> Any:
    kind = definition.type
    if kind in ("text", "long_text"):
        if not isinstance(value, str) or len(value) > definition.max_length:
            raise ValueError("text")
        return value.strip()
    if kind == "select":
        if value not in definition.options:
            raise ValueError("option")
        return value
    if kind == "multi_select":
        if not isinstance(value, list) or any(v not in definition.options for v in value):
            raise ValueError("options")
        return sorted(set(value))
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("number")
        return value
    if kind == "rating":
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
            raise ValueError("rating")
        return value
    if kind == "boolean":
        if not isinstance(value, bool):
            raise ValueError("boolean")
        return value
    if kind == "date":
        return date.fromisoformat(str(value)).isoformat()
    return str(UUID(str(value)))  # user


def validate_values(defs: Sequence[FieldDef], values: Mapping[str, Any]) -> dict[str, Any]:
    known = {d.key: d for d in defs}
    unknown = sorted(set(values) - set(known))
    if unknown:
        raise FieldsInvalid("Unknown fields.", extensions={"fields": unknown})
    missing = [
        d.key for d in defs if d.required and (values.get(d.key) in (None, "", []) or d.key not in values)
    ]
    if missing:
        raise RequiredFieldsMissing(f"Fill in: {', '.join(missing)}.", extensions={"fields": missing})
    out: dict[str, Any] = {}
    invalid: list[str] = []
    for key, value in values.items():
        if value in (None, "", []):
            continue
        try:
            out[key] = _coerce(known[key], value)
        except (ValueError, TypeError):
            invalid.append(key)
    if invalid:
        raise FieldsInvalid("Some fields are not valid.", extensions={"fields": sorted(invalid)})
    return out


def visible_fields(defs: Sequence[FieldDef], values: Mapping[str, Any], *, staff: bool) -> dict[str, Any]:
    staff_only = {d.key for d in defs if d.visibility == "staff_only"}
    return {k: v for k, v in values.items() if staff or k not in staff_only}


BASELINE_TYPES: tuple[dict[str, Any], ...] = (
    {
        "key": "bug",
        "label": "Something is broken",
        "fields": [
            {"key": "steps", "label": "What did you do?", "type": "long_text", "required": True},
            {"key": "expected", "label": "What did you expect?", "type": "long_text"},
            {"key": "impact", "label": "Impact", "type": "select", "options": ["low", "medium", "high"]},
        ],
    },
    {
        "key": "access_request",
        "label": "Access request",
        "fields": [
            {"key": "resource", "label": "What do you need access to?", "type": "text", "required": True},
            {"key": "justification", "label": "Why?", "type": "long_text", "required": True},
            {"key": "staff_notes", "label": "Staff notes", "type": "long_text", "visibility": "staff_only"},
        ],
    },
    {
        "key": "service_issue",
        "label": "A service does not work",
        "fields": [{"key": "since", "label": "Since when?", "type": "date"}],
    },
    {"key": "question", "label": "Question", "fields": []},
    {"key": "other", "label": "Other", "fields": []},
    # #354: « Report a problem » on a media's page works from the start (what is wrong is asked by the page)
    {"key": "media_issue", "label": "A problem with a media", "fields": [], "media": True},
)

BASELINE_FORMS: tuple[dict[str, Any], ...] = (
    {
        "key": "general",
        "kind": "general",
        "label": "General feedback",
        "fields": [
            {"key": "message", "label": "Your feedback", "type": "long_text", "required": True},
            {
                "key": "topic",
                "label": "About",
                "type": "select",
                "options": ["portal", "media", "shop", "community", "support", "other"],
            },
            {"key": "rating", "label": "Your overall rating", "type": "rating"},
        ],
    },
    {
        "key": "bug_report",
        "kind": "bug_report",
        "label": "Report a bug",
        "fields": [
            {"key": "what", "label": "What went wrong?", "type": "text", "required": True},
            {"key": "steps", "label": "How to reproduce", "type": "long_text"},
            {"key": "page", "label": "Page", "type": "text"},
        ],
    },
    {
        "key": "feature_request",
        "kind": "feature_request",
        "label": "Suggest a feature",
        "fields": [
            {"key": "idea", "label": "Your idea", "type": "long_text", "required": True},
            {"key": "why", "label": "Why would it help?", "type": "long_text"},
        ],
    },
)
