"""#68, #70 — the live weather ambience: the WMO code read as a sky, nothing asked while no place is set,
each member's own place before everyone's default, the answer kept 15 minutes per place, any failure
meaning no weather, places found by name."""

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import httpx

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.registry import CapabilityRegistry
from portalab.modules.ui.weather import WeatherService, condition_of


def test_wmo_codes_read_as_skies() -> None:
    assert [condition_of(c) for c in (0, 2, 45, 61, 81, 73, 86, 95, 99)] == [
        "clear", "cloudy", "fog", "rain", "rain", "snow", "snow", "storm", "storm",
    ]  # fmt: skip


class _Config:
    """Everyone's values, and some members' own (the user tier wins, like the real config)."""

    def __init__(self, values: dict[str, Any], own: dict[UUID, dict[str, Any]] | None = None) -> None:
        self.values = values
        self.own = own or {}

    async def get(self, key: str, *, user_id: UUID | None = None) -> Any:
        mine = self.own.get(user_id, {}) if user_id else {}
        return SimpleNamespace(value=mine.get(key, self.values.get(key)))


def _registry(values: dict[str, Any], own: dict[UUID, dict[str, Any]] | None = None) -> CapabilityRegistry:
    registry = CapabilityRegistry()
    from portalab.capabilities.catalog import new_registry

    spec = new_registry().spec(CONFIG)
    registry.declare(spec)
    registry.provide(CONFIG, _Config(values, own), instance_ref="test", owner="test")
    return registry


def _sky(calls: list[httpx.Request]) -> httpx.AsyncClient:
    def answer(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200, json={"current": {"weather_code": 95, "is_day": 0, "temperature_2m": 12.5}}
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(answer))


async def test_asked_once_kept_and_never_without_a_place() -> None:
    calls: list[httpx.Request] = []
    client = _sky(calls)
    nowhere = WeatherService(_registry({}), client)
    assert await nowhere.now() is None and calls == []

    service = WeatherService(_registry({"ui.weather.latitude": 48.85, "ui.weather.longitude": 2.35}), client)
    first = await service.now()
    second = await service.now()
    assert first is not None
    place, weather = first
    assert (place.latitude, place.longitude) == (48.85, 2.35)
    assert weather is not None and weather.condition == "storm" and not weather.is_day
    assert weather.temperature == 12.5
    assert second == first and len(calls) == 1  # kept, not asked again
    assert calls[0].url.params["latitude"] == "48.85"


async def test_each_member_sees_the_sky_over_their_own_place() -> None:
    calls: list[httpx.Request] = []
    alice, bob = uuid4(), uuid4()
    own = {alice: {"ui.weather.latitude": 45.76, "ui.weather.longitude": 4.84, "ui.weather.place": "Lyon"}}
    service = WeatherService(
        _registry({"ui.weather.latitude": 48.85, "ui.weather.longitude": 2.35}, own), _sky(calls)
    )
    mine = await service.now(alice)
    theirs = await service.now(bob)  # no place of their own: everyone's default
    assert mine is not None and mine[0].name == "Lyon" and mine[0].latitude == 45.76
    assert theirs is not None and theirs[0].latitude == 48.85
    assert {c.url.params["latitude"] for c in calls} == {"45.76", "48.85"}  # one question per place


async def test_a_failure_is_no_weather() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    service = WeatherService(_registry({"ui.weather.latitude": 1.0, "ui.weather.longitude": 2.0}), client)
    answer = await service.now()
    assert answer is not None and answer[1] is None


async def test_places_are_found_by_name() -> None:
    asked: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(request)
        return httpx.Response(
            200,
            json={
                "results": [
                    {"name": "Lyon", "admin1": "Auvergne-Rhône-Alpes", "country": "France",
                     "latitude": 45.75, "longitude": 4.85},
                    {"name": "Lyons", "country": "United States", "latitude": 43.06, "longitude": -76.99},
                    {"name": "broken"},
                ]
            },
        )  # fmt: skip

    service = WeatherService(_registry({}), httpx.AsyncClient(transport=httpx.MockTransport(answer)))
    found = await service.places("Lyon", "fr")
    assert [p.name for p in found] == ["Lyon, Auvergne-Rhône-Alpes, France", "Lyons, United States"]
    assert asked[0].url.params["language"] == "fr"
    assert await service.places(" L ") == [] and len(asked) == 1  # too short: nothing asked
