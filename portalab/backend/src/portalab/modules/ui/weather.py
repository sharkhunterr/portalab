"""#68: the weather outside, for the « live weather » ambience — the sky over the homelab (rain, snow,
storm, fog, clouds, clear, by day or night). Asked by the server to Open-Meteo (free, no key, no account)
for the place the administrators set (``ui.weather.latitude`` / ``ui.weather.longitude``; nothing is asked
while they are empty), kept 15 minutes; members' browsers never call anyone. Any failure: no weather."""

import time
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.logging import get_logger

log = get_logger("portalab.ui.weather")

Condition = Literal["clear", "cloudy", "fog", "rain", "snow", "storm"]
URL = "https://api.open-meteo.com/v1/forecast"
KEEP_SECONDS = 15 * 60


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


class WeatherService:
    def __init__(self, capabilities: CapabilityRegistry, client: httpx.AsyncClient | None = None) -> None:
        self.capabilities = capabilities
        self.client = client
        self._kept: tuple[float, tuple[float, float], Weather | None] | None = None

    async def _place(self) -> tuple[float, float] | None:
        providers = self.capabilities.system_providers(CONFIG)
        if not providers:
            return None
        try:
            lat = (await providers[0].provider.get("ui.weather.latitude")).value
            lon = (await providers[0].provider.get("ui.weather.longitude")).value
        except Exception:
            return None
        if lat is None or lon is None:
            return None
        return float(lat), float(lon)

    async def now(self) -> Weather | None:
        place = await self._place()
        if place is None:
            return None
        kept = self._kept
        if kept and kept[1] == place and time.monotonic() - kept[0] < KEEP_SECONDS:
            return kept[2]
        weather = await self._ask(place)
        self._kept = (time.monotonic(), place, weather)
        return weather

    async def _ask(self, place: tuple[float, float]) -> Weather | None:
        params: dict[str, Any] = {
            "latitude": place[0],
            "longitude": place[1],
            "current": "weather_code,is_day,temperature_2m",
        }
        try:
            if self.client is not None:
                response = await self.client.get(URL, params=params, timeout=8)
            else:
                async with httpx.AsyncClient(timeout=8) as client:
                    response = await client.get(URL, params=params)
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
