"""Gamification metrics (T030): grants, withheld by reason, anomalies, spend outcomes, drift — counts only."""

import re
import threading
from collections import Counter

from portalab.core.logging import get_logger

log = get_logger("portalab.gamification")
_METRIC = re.compile(r"^gamification\.[a-z_][a-z0-9_]*(\.[a-z0-9_]+)*$")


class GamificationMetrics:
    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._gauges: dict[str, float] = {}
        self._lock = threading.Lock()

    def increment(self, name: str, amount: int = 1) -> None:
        if not _METRIC.fullmatch(name):
            raise ValueError(f"metric names are fixed identifiers, got {name!r}")
        with self._lock:
            self._counts[name] += amount

    def gauge(self, name: str, value: float) -> None:
        if not _METRIC.fullmatch(name):
            raise ValueError(f"metric names are fixed identifiers, got {name!r}")
        with self._lock:
            self._gauges[name] = value

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return {**self._counts, **self._gauges}


metrics = GamificationMetrics()
