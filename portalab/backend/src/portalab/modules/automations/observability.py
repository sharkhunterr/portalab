"""Automation metrics (T032): executions by status, durations, suspensions, loop/storm preventions,
approval latency — counts only, never payloads."""

import re
import threading
from collections import Counter

from portalab.core.logging import get_logger

log = get_logger("portalab.automations")
_METRIC = re.compile(r"^automations\.[a-z_][a-z0-9_]*(\.[a-z0-9_]+)*$")


class AutomationMetrics:
    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._lock = threading.Lock()

    def increment(self, name: str, amount: int = 1) -> None:
        if not _METRIC.fullmatch(name):
            raise ValueError(f"metric names are fixed identifiers, got {name!r}")
        with self._lock:
            self._counts[name] += amount

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)


metrics = AutomationMetrics()
