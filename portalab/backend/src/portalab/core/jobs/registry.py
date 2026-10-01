"""Job handler registry keyed by ``kind``.

Delivery is at-least-once, so every handler must declare its idempotency expectation (how a duplicate
delivery is made harmless). Registrations are owner-tagged for clean removal (spec 023).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

Handler = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class JobHandler:
    kind: str
    func: Handler
    idempotency: str
    timeout_seconds: float
    owner: str


class JobRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, JobHandler] = {}

    def register(
        self,
        kind: str,
        func: Handler,
        *,
        idempotency: str,
        timeout_seconds: float = 60.0,
        owner: str = "core",
    ) -> JobHandler:
        if not idempotency.strip():
            raise ValueError(f"handler {kind!r} must declare its idempotency expectation")
        if kind in self._handlers:
            raise ValueError(f"a handler for {kind!r} is already registered")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        handler = JobHandler(kind, func, idempotency.strip(), timeout_seconds, owner)
        self._handlers[kind] = handler
        return handler

    def handler(
        self, kind: str, *, idempotency: str, timeout_seconds: float = 60.0, owner: str = "core"
    ) -> Callable[[Handler], Handler]:
        def decorator(func: Handler) -> Handler:
            self.register(kind, func, idempotency=idempotency, timeout_seconds=timeout_seconds, owner=owner)
            return func

        return decorator

    def get(self, kind: str) -> JobHandler | None:
        return self._handlers.get(kind)

    def kinds(self) -> list[str]:
        return sorted(self._handlers)

    def unregister(self, owner: str) -> int:
        doomed = [kind for kind, handler in self._handlers.items() if handler.owner == owner]
        for kind in doomed:
            del self._handlers[kind]
        return len(doomed)


default_registry = JobRegistry()
