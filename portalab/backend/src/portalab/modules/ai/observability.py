"""AI metrics (T032): provider latency/errors, tokens, tool-call outcomes, pending-action funnel and guard
trips — ids and counts only, never prompts or answers."""

import re
import threading
from collections import Counter

from portalab.core.logging import get_logger

log = get_logger("portalab.ai")
_METRIC = re.compile(r"^ai\.[a-z_][a-z0-9_]*(\.[a-z0-9_]+)*$")


class AiMetrics:
    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._latest: dict[str, float] = {}
        self._lock = threading.Lock()

    def _check(self, name: str) -> None:
        if not _METRIC.fullmatch(name):
            raise ValueError(f"metric names are fixed identifiers, got {name!r}")

    def increment(self, name: str, amount: int = 1) -> None:
        self._check(name)
        with self._lock:
            self._counts[name] += amount

    def observe(self, name: str, value: float) -> None:
        self._check(name)
        with self._lock:
            self._latest[name] = round(value, 1)

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return {**self._counts, **self._latest}

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()
            self._latest.clear()


metrics = AiMetrics()
