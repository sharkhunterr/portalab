"""Retention targets (spec 021 R4): what may be cleaned up, how, and what must never be touched.

Modules declare targets in code; the Privacy retention engine applies the configured windows
(``privacy.retention.<class>.days``). ``integrity_necessary`` targets (ledgers, transactions) are never
deleted; append-only stores are retained by dropping whole time partitions (R5), never row by row.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Literal

from portalab.capabilities.visibility import DATA_CLASSES, DataClass

Action = Literal["delete", "anonymize", "aggregate", "drop_partition"]


class RetentionTargetError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RetentionTarget:
    name: str
    table: str  # "schema.table"
    data_class: DataClass
    timestamp_column: str
    action: Action
    owner: str
    integrity_necessary: bool = False
    extra_condition: str | None = None  # constant SQL predicate written by the owner, never user input
    window: Callable[[], timedelta | None] | None = field(default=None, compare=False)  # owner-defined window


class RetentionRegistry:
    def __init__(self) -> None:
        self._targets: dict[str, RetentionTarget] = {}

    def register(self, target: RetentionTarget) -> RetentionTarget:
        if target.data_class not in DATA_CLASSES:
            raise RetentionTargetError(f"unknown data class {target.data_class!r}")
        if target.integrity_necessary and target.action in ("delete", "anonymize"):
            raise RetentionTargetError(
                f"{target.name}: integrity-necessary data is never deleted or anonymized"
            )
        if "." not in target.table:
            raise RetentionTargetError("table must be schema-qualified")
        self._targets[target.name] = target
        return target

    def all(self) -> list[RetentionTarget]:
        return [self._targets[name] for name in sorted(self._targets)]

    def unregister(self, owner: str) -> int:
        doomed = [name for name, target in self._targets.items() if target.owner == owner]
        for name in doomed:
            del self._targets[name]
        return len(doomed)


default_retention_targets = RetentionRegistry()
register_retention_target: Callable[[RetentionTarget], RetentionTarget] = default_retention_targets.register
