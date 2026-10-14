"""Service signals (issue 122): what a service says at a given moment, watched for automations — a parity
check running on a server, the plays under way on a media server, the containers with an update…

A module declares a ``Signal`` over one of its service capabilities: a stable key, a label, a kind and a
``read(service_id, provider)`` giving the current value (``None``: unknown now — never a change). The
automations watch them and publish ``service.signal_changed`` when a value changes, so any automation can
react to any service's data with the usual event trigger and filters (``signal``, ``value``,
``service_id``)."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

SignalKind = Literal["bool", "number", "text"]
Value = bool | int | float | str


@dataclass(frozen=True, slots=True)
class Signal:
    key: str  # « infrastructure.parity_running »
    owner: str
    capability: str  # the service capability it reads (each of its providers is one service)
    kind: SignalKind
    read: Callable[[str, Any], Awaitable[Value | None]]
    label: str = ""
    description: str = ""


class SignalRegistry:
    def __init__(self) -> None:
        self._signals: dict[str, Signal] = {}

    def register(self, signal: Signal) -> Signal:
        existing = self._signals.get(signal.key)
        if existing is not None and existing.owner != signal.owner:
            raise ValueError(f"signal {signal.key!r} is already declared by {existing.owner}")
        self._signals[signal.key] = signal
        return signal

    def get(self, key: str) -> Signal | None:
        return self._signals.get(key)

    def all(self) -> list[Signal]:
        return [self._signals[key] for key in sorted(self._signals)]


default_signals = SignalRegistry()
