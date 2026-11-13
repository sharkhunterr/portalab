"""Redaction (T009, T033): secret-looking keys never reach the model, the UI, logs or audit; tool data is
size-capped; known secret values (the provider key, MCP credentials) are masked in any text."""

import json
import re
from collections.abc import Iterable
from typing import Any

SECRET_KEY = re.compile(
    r"(pass(word)?|secret|token|api[_-]?key|credential|authorization|cookie|private)", re.IGNORECASE
)
MASK = "[redacted]"
MAX_DATA = 8_000


def redact(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        return "…"
    if isinstance(value, dict):
        return {
            str(k): (MASK if SECRET_KEY.search(str(k)) else redact(v, depth + 1)) for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact(v, depth + 1) for v in list(value)[:100]]
    if isinstance(value, str):
        return value[:4000]
    if value is None or isinstance(value, bool | int | float):
        return value
    return str(value)[:4000]


def cap(value: Any, limit: int = MAX_DATA) -> Any:
    text = json.dumps(value, default=str, ensure_ascii=False)
    if len(text) <= limit:
        return value
    return {"truncated": True, "preview": text[:limit]}


def mask_secrets(text: str, secrets: Iterable[str | None]) -> str:
    for secret in secrets:
        if secret and len(secret) >= 6:
            text = text.replace(secret, MASK)
    return text
