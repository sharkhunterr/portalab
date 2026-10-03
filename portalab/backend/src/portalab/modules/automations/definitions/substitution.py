"""Closed substitution (R1): parameters may reference ``${event.<declared field>}``, ``${event.occurred_at}``,
``${event.id}``, ``${subject.id}``, ``${subject.type}``, ``${actor.id}``, ``${automation.key}`` and
``${steps.<earlier step>.<key>}`` — nothing else, never an expression. Values are inserted as text."""

import re
from collections.abc import Iterator, Mapping
from typing import Any

PLACEHOLDER = re.compile(r"\$\{([a-z][a-z0-9_]*(?:\.[a-z0-9_]+){1,2})\}")
FIXED = {"event.occurred_at", "event.id", "subject.id", "subject.type", "actor.id", "automation.key"}


def references(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield from (m.group(1) for m in PLACEHOLDER.finditer(value))
        if "${" in PLACEHOLDER.sub("", value):
            yield "__invalid__"
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from references(item)
    elif isinstance(value, list):
        for item in value:
            yield from references(item)


def substitute(value: Any, scope: Mapping[str, Any], *, keep_missing: bool = False) -> Any:
    """``keep_missing`` leaves unresolved placeholders in place (outputs of steps not run yet)."""

    def one(match: re.Match[str]) -> str:
        if match.group(1) in scope:
            return "" if scope[match.group(1)] is None else str(scope[match.group(1)])
        return match.group(0) if keep_missing else ""

    if isinstance(value, str):
        whole = PLACEHOLDER.fullmatch(value)
        if whole is not None and whole.group(1) in scope:
            resolved = scope[whole.group(1)]
            return (
                resolved
                if resolved is None or isinstance(resolved, str | int | float | bool)
                else str(resolved)
            )
        return PLACEHOLDER.sub(one, value)
    if isinstance(value, Mapping):
        return {k: substitute(v, scope, keep_missing=keep_missing) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, scope, keep_missing=keep_missing) for v in value]
    return value
