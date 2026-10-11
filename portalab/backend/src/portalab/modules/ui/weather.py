"""#68, #70: the weather outside, for the « live weather » ambience — the sky over the member's place (rain,
snow, storm, fog, clouds, clear, by day or night). Each member picks their own place (``ui.weather.latitude``
/ ``ui.weather.longitude`` / ``ui.weather.place``, found by name with :meth:`WeatherService.places`); the
value the administrators set is everyone's default; nothing is asked while there is none. Asked by the server
to Open-Meteo (free, no key, no account), each place kept 15 minutes; members' browsers never call anyone.
Any failure: no weather."""

import time
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

import httpx

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.logging import get_logger

log = get_logger("portalab.ui.weather")

Condition = Literal["clear", "cloudy", "fog", "rain", "snow", "storm"]
URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
KEEP_SECONDS = 15 * 60
KEPT_PLACES = 500  # places kept at once (each member may have their own)


def condition_of(code: int) -> Condition:
    """The WMO weather code (Open-Meteo's ``weather_code``) as one of the ambience's skies."""
    if code >= 95:
        return "storm"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "rain"
    if code in (45, 48):
        return "fog"
    if code in (1, 2, 3):
        return "cloudy"
    return "clear"


@dataclass(frozen=True, slots=True)
class Weather:
    condition: Condition
    is_day: bool
    temperature: float | None


@dataclass(frozen=True, slots=True)
class Place:
    latitude: float
    longitude: float
    name: str | None = None


class WeatherService:
    def __init__(self, capabilities: CapabilityRegistry, client: httpx.AsyncClient | None = None) -> None:
        self.capabilities = capabilities
        self.client = client
        self._kept: dict[tuple[float, float], tuple[float, Weather | None]] = {}

    async def place(self, user_id: UUID | None = None) -> Place | None:
        """The member's place (or everyone's default), ``None`` when there is none."""
        providers = self.capabilities.system_providers(CONFIG)
        if not providers:
            return None
        config = providers[0].provider
        try:
            lat = (await config.get("ui.weather.latitude", user_id=user_id)).value
            lon = (await config.get("ui.weather.longitude", user_id=user_id)).value
            name = (await config.get("ui.weather.place", user_id=user_id)).value
        except Exception:
            return None
        if lat is None or lon is None:
            return None
        return Place(float(lat), float(lon), str(name) if name else None)

    async def now(self, user_id: UUID | None = None) -> tuple[Place, Weather | None] | None:
        place = await self.place(user_id)
        if place is None:
            return None
        key = (round(place.latitude, 2), round(place.longitude, 2))  # neighbours share one question
        kept = self._kept.get(key)
        if kept and time.monotonic() - kept[0] < KEEP_SECONDS:
            return place, kept[1]
        weather = await self._ask(key)
        if len(self._kept) >= KEPT_PLACES:
            self._kept.pop(next(iter(self._kept)))
        self._kept[key] = (time.monotonic(), weather)
        return place, weather

    async def _get(self, url: str, params: dict[str, Any]) -> httpx.Response:
        if self.client is not None:
            return await self.client.get(url, params=params, timeout=8)
        async with httpx.AsyncClient(timeout=8) as client:
            return await client.get(url, params=params)

    async def _ask(self, place: tuple[float, float]) -> Weather | None:
        params: dict[str, Any] = {
            "latitude": place[0],
            "longitude": place[1],
            "current": "weather_code,is_day,temperature_2m",
        }
        try:
            response = await self._get(URL, params)
            response.raise_for_status()
            current = response.json().get("current") or {}
            return Weather(
                condition_of(int(current.get("weather_code", 0))),
                bool(current.get("is_day", 1)),
                float(current["temperature_2m"]) if current.get("temperature_2m") is not None else None,
            )
        except Exception as exc:
            log.warning("weather unavailable", extra={"fields": {"error": type(exc).__name__}})
            return None

    async def places(self, query: str, language: str = "en") -> list[Place]:
        """#70: places matching a name (a town, a city), for a member to pick theirs."""
        query = query.strip()
        if len(query) < 2:
            return []
        try:
            response = await self._get(
                GEOCODING_URL, {"name": query[:80], "count": 6, "language": language, "format": "json"}
            )
            response.raise_for_status()
            found = response.json().get("results") or []
        except Exception as exc:
            log.warning("place search unavailable", extra={"fields": {"error": type(exc).__name__}})
            return []
        places: list[Place] = []
        for row in found:
            try:
                parts = [row.get("name"), row.get("admin1"), row.get("country")]
                name = ", ".join(dict.fromkeys(str(p) for p in parts if p))
                places.append(Place(float(row["latitude"]), float(row["longitude"]), name))
            except (KeyError, TypeError, ValueError):
                continue
        return places
