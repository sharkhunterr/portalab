"""#68, #70, #88 — the live weather ambience: every WMO code read as its own sky and intensity, the hour's
light at the place (dawn, day, dusk, night), the wind, nothing asked while no place is set, each member's own
place before everyone's default, the answer kept 15 minutes per place, any failure meaning no weather,
places found by name."""

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import httpx

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.registry import CapabilityRegistry
from portalab.modules.ui.weather import CODES, WeatherService, condition_of, read_weather


def test_wmo_codes_read_as_skies() -> None:
    assert [condition_of(c)[0] for c in (0, 1, 2, 3, 45, 48)] == [
        "clear", "mainly_clear", "partly_cloudy", "overcast", "fog", "rime_fog",
    ]  # fmt: skip
    assert [condition_of(c) for c in (51, 57, 61, 65, 66, 81, 82)] == [
        ("drizzle", "light"), ("freezing_drizzle", "heavy"), ("rain", "light"), ("rain", "heavy"),
        ("freezing_rain", "light"), ("showers", "moderate"), ("showers", "heavy"),
    ]  # fmt: skip
    assert [condition_of(c) for c in (71, 75, 77, 86, 95, 96, 99)] == [
        ("snow", "light"), ("snow", "heavy"), ("snow_grains", "light"), ("snow_showers", "heavy"),
        ("storm", "moderate"), ("storm_hail", "moderate"), ("storm_hail", "heavy"),
    ]  # fmt: skip
    assert condition_of(97) == ("storm", "moderate") and condition_of(68) == ("rain", "moderate")
    assert len({c for c, _ in CODES.values()}) == 16  # every sky the code may tell (four more: below)


def test_the_light_and_the_wind_at_the_place() -> None:
    daily = {"sunrise": ["2026-10-15T08:12"], "sunset": ["2026-10-15T19:01"]}

    def at(time: str, is_day: int, **current: float) -> dict[str, object]:
        answer = {"current": {"time": time, "is_day": is_day, "weather_code": 2, **current}, "daily": daily}
        return {**answer, "timezone": "Europe/Paris"}

    assert read_weather(at("2026-10-15T07:45", 0)).phase == "dawn"  # before sunrise, already light
    assert read_weather(at("2026-10-15T12:00", 1)).phase == "day"
    assert read_weather(at("2026-10-15T19:30", 0)).phase == "dusk"
    calm = read_weather(at("2026-10-15T23:00", 0, wind_speed_10m=12.0, cloud_cover=75))
    assert calm.phase == "night" and not calm.windy and calm.cloud_cover == 75
    assert calm.condition == "partly_cloudy" and calm.timezone == "Europe/Paris"
    assert read_weather(at("2026-10-15T12:00", 1, wind_speed_10m=20.0, wind_gusts_10m=70.0)).windy
    assert read_weather({}).condition == "clear"  # an empty answer is no crash


def test_the_skies_the_code_does_not_tell() -> None:
    def sky(code: int, **current: float) -> str:
        return read_weather({"current": {"weather_code": code, "is_day": 1, **current}}).condition

    assert sky(2, cloud_cover_high=80, cloud_cover_low=5, cloud_cover_mid=10) == "hazy"
    assert sky(2, cloud_cover_high=80, cloud_cover_low=60) == "partly_cloudy"  # low clouds: not a veil
    assert sky(1, visibility=2500) == "mist"
    assert sky(45, visibility=200) == "fog"  # fog stays fog
    assert sky(63, rain=1.2, snowfall=0.4) == "sleet"
    assert sky(73, snowfall=1.0, showers=0.3) == "sleet"
    assert sky(63, rain=1.2) == "rain"
    assert sky(1, wind_speed_10m=20, wind_gusts_10m=70) == "windy"
    assert sky(3, wind_gusts_10m=70) == "overcast"  # an overcast sky keeps its look, blown


class _Config:
    """Everyone's values, and some members' own (the user tier wins, like the real config)."""

    def __init__(self, values: dict[str, Any], own: dict[UUID, dict[str, Any]] | None = None) -> None:
        self.values = values
        self.own = own or {}

    async def get(self, key: str, *, user_id: UUID | None = None) -> Any:
        mine = self.own.get(user_id, {}) if user_id else {}
        if key in mine:
            return SimpleNamespace(value=mine[key], source="user")
        return SimpleNamespace(value=self.values.get(key), source="global")


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
        current = {"weather_code": 95, "is_day": 0, "temperature_2m": 12.5, "wind_gusts_10m": 80}
        return httpx.Response(200, json={"current": current})

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
    assert weather.temperature == 12.5 and weather.windy and weather.phase == "night"
    assert weather.fetched_at is not None and weather.fetched_at.endswith("+00:00")  # when it was asked
    assert second == first and len(calls) == 1  # kept, not asked again
    assert calls[0].url.params["latitude"] == "48.85"
    assert calls[0].url.params["timezone"] == "auto"  # the place's own clock


async def test_each_member_sees_the_sky_over_their_own_place() -> None:
    calls: list[httpx.Request] = []
    alice, bob = uuid4(), uuid4()
    own = {alice: {"ui.weather.latitude": 45.76, "ui.weather.longitude": 4.84, "ui.weather.place": "Lyon"}}
    service = WeatherService(
        _registry({"ui.weather.latitude": 48.85, "ui.weather.longitude": 2.35}, own), _sky(calls)
    )
    mine = await service.now(alice)
    theirs = await service.now(bob)  # no place of their own: everyone's default
    assert mine is not None and mine[0].name == "Lyon" and mine[0].latitude == 45.76 and mine[0].own
    assert theirs is not None and theirs[0].latitude == 48.85 and not theirs[0].own
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
                     "country_code": "fr", "population": 522969, "latitude": 45.75, "longitude": 4.85},
                    {"name": "Lyons", "country": "United States", "latitude": 43.06, "longitude": -76.99},
                    {"name": "broken"},
                ]
            },
        )  # fmt: skip

    service = WeatherService(_registry({}), httpx.AsyncClient(transport=httpx.MockTransport(answer)))
    found = await service.places("Lyon", "fr")
    assert [p.label for p in found] == ["Lyon, Auvergne-Rhône-Alpes, France", "Lyons, United States"]
    assert (found[0].name, found[0].region, found[0].country_code) == ("Lyon", "Auvergne-Rhône-Alpes", "FR")
    assert found[0].population == 522969 and found[1].region is None
    assert asked[0].url.params["language"] == "fr"
    assert await service.places(" L ") == [] and len(asked) == 1  # too short: nothing asked
