"""027: the worker provides the enabled services' capabilities at start and refreshes them periodically
(images, playback and requests run in the worker; services enabled from the web process are picked up)."""

import asyncio
from typing import Any

from portalab.app import worker


class _Platform:
    def __init__(self) -> None:
        self.calls = 0
        self.third = asyncio.Event()

    async def start_services(self) -> bool:
        self.calls += 1
        if self.calls >= 3:
            self.third.set()
        return self.calls > 1  # the first round fails, the next ones succeed


async def test_services_are_provided_and_refreshed(monkeypatch: Any) -> None:
    monkeypatch.setattr(worker, "SERVICES_REFRESH_SECONDS", 0.01)
    platform, stop = _Platform(), asyncio.Event()
    task = asyncio.create_task(worker.provide_services(platform, stop))  # type: ignore[arg-type]
    await asyncio.wait_for(platform.third.wait(), timeout=1)
    stop.set()
    await asyncio.wait_for(task, timeout=1)
    assert platform.calls >= 3  # a failed round never stops the loop
