"""Event-type registry and payload validation (T007; R4, R7).

The registry itself is the capability-layer contract (:mod:`portalab.capabilities.events`) so producers
declare their types without importing this module. Validation turns a publication into either a normalized
payload or a quarantine reason: unknown type, unsupported (newer) version, secret-like or personal-looking
keys, or a payload that does not match the declared schema.
"""

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from portalab.capabilities.events import EventType, EventTypeRegistry
from portalab.core.jobs.queue import check_payload
from portalab.core.privacy_registry import looks_personal

ALLOWED_PERSONAL_LOOKING = frozenset({"display_name_changed"})  # explicit allow-list (none needed so far)


@dataclass(frozen=True, slots=True)
class Validation:
    payload: dict[str, Any] | None
    reason: str | None = None
    detail: str = ""


def _personal_keys(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            name = str(key)
            if looks_personal(name) and name not in ALLOWED_PERSONAL_LOOKING:
                found.append(f"{path}{name}")
            found.extend(_personal_keys(item, f"{path}{name}."))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_personal_keys(item, f"{path}{index}."))
    return found


def validate(registry: EventTypeRegistry, name: str, version: int, payload: dict[str, Any]) -> Validation:
    event_type: EventType | None = registry.get(name)
    if event_type is None:
        return Validation(None, "unknown_type", f"{name} is not a registered event type")
    if version > event_type.version:
        return Validation(
            None, "version_unsupported", f"{name} v{version} is newer than v{event_type.version}"
        )
    try:
        check_payload(payload)
    except ValueError as exc:
        return Validation(None, "invalid_payload", str(exc))
    personal = _personal_keys(payload)
    if personal:
        return Validation(None, "pii_detected", f"personal-looking fields: {', '.join(sorted(personal))}")
    try:
        normalized = json.loads(json.dumps(payload, default=str))
    except (TypeError, ValueError) as exc:
        return Validation(None, "invalid_payload", f"payload is not serializable: {type(exc).__name__}")
    if event_type.schema is not None:
        extra = set(normalized) - set(event_type.schema.model_fields)
        if extra and not event_type.open_payload:
            return Validation(None, "invalid_payload", f"undeclared fields: {', '.join(sorted(extra))}")
        try:
            model = event_type.schema.model_validate(normalized)
        except ValidationError as exc:
            return Validation(None, "invalid_payload", f"{exc.error_count()} schema error(s)")
        validated = model.model_dump(mode="json")
        if event_type.open_payload:
            validated = {**normalized, **validated}
        normalized = validated
    return Validation(normalized)
