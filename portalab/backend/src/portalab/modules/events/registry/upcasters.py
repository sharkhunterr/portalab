"""Payload upcasters (T019; FR-003): stored events keep their original version; consumers understanding a
newer version receive an upcast copy. Owner-tagged for clean removal."""

from collections.abc import Callable
from typing import Any

Upcaster = Callable[[dict[str, Any]], dict[str, Any]]


class UpcasterRegistry:
    def __init__(self) -> None:
        self._steps: dict[tuple[str, int], tuple[Upcaster, str]] = {}

    def register(self, event_type: str, from_version: int, upcaster: Upcaster, *, owner: str) -> None:
        slot = (event_type, from_version)
        if slot in self._steps:
            raise ValueError(f"an upcaster for {event_type} v{from_version} exists")
        self._steps[slot] = (upcaster, owner)

    def upcast(
        self, event_type: str, payload: dict[str, Any], from_version: int, to_version: int
    ) -> dict[str, Any]:
        for version in range(from_version, to_version):
            step = self._steps.get((event_type, version))
            if step is None:
                raise LookupError(f"no upcaster for {event_type} v{version} → v{version + 1}")
            payload = step[0](dict(payload))
        return payload

    def unregister(self, owner: str) -> int:
        doomed = [slot for slot, (_, who) in self._steps.items() if who == owner]
        for slot in doomed:
            del self._steps[slot]
        return len(doomed)


default_upcasters = UpcasterRegistry()
