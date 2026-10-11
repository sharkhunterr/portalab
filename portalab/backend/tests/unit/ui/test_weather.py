"""#68 — the live weather ambience: the WMO code read as a sky, nothing asked while no place is set, the
answer kept 15 minutes, any failure meaning no weather."""

from types import SimpleNamespace
from typing import Any

import httpx

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.registry import CapabilityRegistry
from portalab.modules.ui.weather import WeatherService, condition_of


def test_wmo_codes_read_as_skies() -> None:
    assert [condition_of(c) for c in (0, 2, 45, 61, 81, 73, 86, 95, 99)] == [
        "clear", "cloudy", "fog", "rain", "rain", "snow", "snow", "storm", "storm",
    ]  # fmt: skip


class _Config:
    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values

    async def get(self, key: str) -> Any:
        return SimpleNamespace(value=self.values.get(key))


def _registry(values: dict[str, Any]) -> CapabilityRegistry:
    registry = CapabilityRegistry()
    from portalab.capabilities.catalog import new_registry

    spec = new_registry().spec(CONFIG)
    registry.declare(spec)
    registry.provide(CONFIG, _Config(values), instance_ref="test", owner="test")
    return registry


async def test_asked_once_kept_and_never_without_a_place() -> None:
    calls: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200, json={"current": {"weather_code": 95, "is_day": 0, "temperature_2m": 12.5}}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(answer))
    nowhere = WeatherService(_registry({}), client)
    assert await nowhere.now() is None and calls == []

    service = WeatherService(_registry({"ui.weather.latitude": 48.85, "ui.weather.longitude": 2.35}), client)
    first = await service.now()
    second = await service.now()
    assert first is not None and first.condition == "storm" and not first.is_day and first.temperature == 12.5
    assert second == first and len(calls) == 1  # kept, not asked again
    assert calls[0].url.params["latitude"] == "48.85"


async def test_a_failure_is_no_weather() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    service = WeatherService(_registry({"ui.weather.latitude": 1.0, "ui.weather.longitude": 2.0}), client)
    assert await service.now() is None
