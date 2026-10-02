"""I18n metrics (T033): per-service state, last success, run duration/counts, breaker state and call
latency. Service ids and connector keys only — never configuration values, hosts or credentials."""

import re
import threading
from collections import Counter

from portalab.core.logging import get_logger

log = get_logger("portalab.i18n")

_METRIC = re.compile(r"^i18n\.[a-z_]+(\.[a-z0-9_]+)*$")


def metric_part(value: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", value.lower())


class I18nMetrics:
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

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()
            self._gauges.clear()


metrics = I18nMetrics()
