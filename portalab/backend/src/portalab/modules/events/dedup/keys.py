"""Deduplication keys (T010; CD-012, FR-010..014).

Priority: an explicit key given by the producer ▸ a reliable source id ``(source, source_event_id)`` ▸ a
deterministic composite of the type's declared ``dedup_fields``. A key made of a timestamp alone is refused,
and ``received_at`` never takes part in identity. Without any of these, events are not deduplicated (each
publication is a distinct occurrence).
"""

import hashlib
import json
import re
from typing import Any

from portalab.capabilities.events import EventType

_TIMESTAMP_ONLY = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?(Z|[+-]\d{2}:?\d{2})?|\d{9,}(\.\d+)?)\s*$"
)


class DedupKeyError(ValueError):
    pass


def derive(
    event_type: EventType,
    payload: dict[str, Any],
    *,
    source: str,
    source_event_id: str | None,
    explicit: str | None,
) -> str | None:
    if explicit is not None:
        if not explicit.strip() or _TIMESTAMP_ONLY.match(explicit):
            raise DedupKeyError("a deduplication key must not be empty nor a timestamp alone")
        return explicit
    if event_type.source_id_reliable and source_event_id:
        return f"src:{source}:{source_event_id}"
    if event_type.dedup_fields:
        missing = [name for name in event_type.dedup_fields if name not in payload]
        if missing:
            raise DedupKeyError(f"missing deduplication fields {missing}")
        values = [payload[name] for name in event_type.dedup_fields]
        if len(values) == 1 and isinstance(values[0], str) and _TIMESTAMP_ONLY.match(values[0]):
            raise DedupKeyError("deduplication fields must not be a timestamp alone")
        canonical = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)
        return "f:" + hashlib.sha256(canonical.encode()).hexdigest()
    return None
