"""#68, #70, #88: the weather outside, for the « live weather » ambience — the sky over the member's place, as
precisely as the forecast says it: clear, a few clouds or overcast, fog or rime, drizzle, rain or showers
(light to violent, freezing or not), snow, snow grains or snow showers, a thunderstorm with or without hail,
the wind, the clouds' cover, and the light of the hour there (dawn, day, dusk, night — the place's own
clock, never the server's nor the browser's).

Each member picks their own place (``ui.weather.latitude`` / ``ui.weather.longitude`` / ``ui.weather.place``,
found by name with :meth:`WeatherService.places`); the value the administrators set is everyone's default;
nothing is asked while there is none. Asked by the server to Open-Meteo (free, no key, no account), each
place kept 15 minutes; members' browsers never call anyone. Any failure: no weather."""

import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

import httpx

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.logging import get_logger

log = get_logger("portalab.ui.weather")

Condition = Literal[
    "clear",
    "mainly_clear",
    "partly_cloudy",
    "overcast",
    "fog",
    "rime_fog",
    "drizzle",
    "freezing_drizzle",
    "rain",
    "freezing_rain",
    "showers",
    "snow",
    "snow_grains",
    "snow_showers",
    "storm",
    "storm_hail",
    # #88: told by the other measures, not by the code
    "hazy",  # a veil of high clouds, the sun milky through it
    "mist",  # a haze lowering how far one sees, short of fog
    "sleet",  # rain and snow together
    "windy",  # a fair sky blown by a strong wind
]
Intensity = Literal["light", "moderate", "heavy"]
Phase = Literal["dawn", "day", "dusk", "night"]
URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
KEEP_SECONDS = 15 * 60
KEPT_PLACES = 500  # places kept at once (each member may have their own)
TWILIGHT = timedelta(minutes=40)  # either side of sunrise and sunset: dawn, dusk
WINDY_KMH, GUSTY_KMH = 35.0, 55.0
CURRENT = (
    "weather_code,is_day,temperature_2m,apparent_temperature,relative_humidity_2m,cloud_cover,"
    "cloud_cover_low,cloud_cover_mid,cloud_cover_high,visibility,rain,showers,snowfall,"
    "precipitation,wind_speed_10m,wind_gusts_10m,wind_direction_10m"
)
FAIR: tuple[Condition, ...] = ("clear", "mainly_clear", "partly_cloudy", "overcast")
WET: tuple[Condition, ...] = ("drizzle", "rain", "showers")
SNOWY: tuple[Condition, ...] = ("snow", "snow_grains", "snow_showers")
MIST_METRES = 5000.0

# the WMO code (Open-Meteo's ``weather_code``): the sky, and how hard it falls
CODES: dict[int, tuple[Condition, Intensity | None]] = {
    0: ("clear", None),
    1: ("mainly_clear", None),
    2: ("partly_cloudy", None),
    3: ("overcast", None),
    45: ("fog", None),
    48: ("rime_fog", None),
    51: ("drizzle", "light"),
    53: ("drizzle", "moderate"),
    55: ("drizzle", "heavy"),
    56: ("freezing_drizzle", "light"),
    57: ("freezing_drizzle", "heavy"),
    61: ("rain", "light"),
    63: ("rain", "moderate"),
    65: ("rain", "heavy"),
    66: ("freezing_rain", "light"),
    67: ("freezing_rain", "heavy"),
    71: ("snow", "light"),
    73: ("snow", "moderate"),
    75: ("snow", "heavy"),
    77: ("snow_grains", "light"),
    80: ("showers", "light"),
    81: ("showers", "moderate"),
    82: ("showers", "heavy"),
    85: ("snow_showers", "light"),
    86: ("snow_showers", "heavy"),
    95: ("storm", "moderate"),
    96: ("storm_hail", "moderate"),
    99: ("storm_hail", "heavy"),
}


def condition_of(code: int) -> tuple[Condition, Intensity | None]:
    """The WMO weather code as one of the ambience's skies and its intensity; a code the table does not
    know is read by its family (``9x`` a storm, ``7x`` snow…)."""
    if code in CODES:
        return CODES[code]
    if code >= 95:
        return "storm", "moderate"
    if 85 <= code <= 86:
        return "snow_showers", "moderate"
    if 80 <= code <= 84:
        return "showers", "moderate"
    if 70 <= code <= 79:
        return "snow", "moderate"
    if 60 <= code <= 69:
        return "rain", "moderate"
    if 50 <= code <= 59:
        return "drizzle", "moderate"
    if 40 <= code <= 49:
        return "fog", None
    return "clear", None


def refine(condition: Condition, current: dict[str, Any], windy: bool) -> Condition:
    """#88: the skies the WMO code does not tell, from the other measures — rain and snow together (sleet),
    a veil of high clouds (hazy), a haze short of fog (mist), a fair sky in a strong wind (windy)."""
    rain = (_number(current.get("rain")) or 0) + (_number(current.get("showers")) or 0)
    snowfall = _number(current.get("snowfall")) or 0
    if (condition in WET and snowfall > 0) or (condition in SNOWY and rain > 0):
        return "sleet"
    if condition not in FAIR:
        return condition
    visibility = _number(current.get("visibility"))
    if visibility is not None and visibility < MIST_METRES:
        return "mist"
    if windy and condition != "overcast":
        return "windy"
    low, mid = _number(current.get("cloud_cover_low")) or 0, _number(current.get("cloud_cover_mid")) or 0
    high = _number(current.get("cloud_cover_high")) or 0
    if condition != "clear" and high >= 50 and max(low, mid) < 30:
        return "hazy"
    return condition


def phase_of(now: datetime | None, sunrise: datetime | None, sunset: datetime | None, is_day: bool) -> Phase:
    """Dawn and dusk around the place's own sunrise and sunset; otherwise day or night, as forecast."""
    if now is not None and sunrise is not None and abs(now - sunrise) <= TWILIGHT:
        return "dawn"
    if now is not None and sunset is not None and abs(now - sunset) <= TWILIGHT:
        return "dusk"
    return "day" if is_day else "night"


@dataclass(frozen=True, slots=True)
class Weather:
    condition: Condition
    is_day: bool
    temperature: float | None
    intensity: Intensity | None = None
    code: int = 0
    phase: Phase = "day"
    feels_like: float | None = None
    humidity: float | None = None
    cloud_cover: float | None = None
    precipitation: float | None = None  # mm in the last quarter of an hour
    wind_speed: float | None = None  # km/h
    wind_gusts: float | None = None
    wind_direction: float | None = None  # degrees, where it blows from
    windy: bool = False
    visibility: float | None = None  # metres
    local_time: str | None = None  # « 2026-10-15T07:30 », the place's clock
    sunrise: str | None = None
    sunset: str | None = None
    timezone: str | None = None
    fetched_at: str | None = None  # when the server asked for it (UTC, ISO 8601)


@dataclass(frozen=True, slots=True)
class Place:
    latitude: float
    longitude: float
    name: str | None = None
    own: bool = False  # the member's own place, not the portal's default


@dataclass(frozen=True, slots=True)
class Found:
    """A place matching a search: its parts, to show them apart."""

    latitude: float
    longitude: float
    name: str
    label: str  # « Lyon, Auvergne-Rhône-Alpes, France », what is saved
    region: str | None = None
    country: str | None = None
    country_code: str | None = None
    population: int | None = None


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _moment(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def read_weather(answer: dict[str, Any]) -> Weather:
    """Open-Meteo's answer (``current`` and today's ``daily`` sunrise and sunset) as the ambience's sky."""
    current = answer.get("current") or {}
    daily = answer.get("daily") or {}
    code = int(current.get("weather_code") or 0)
    condition, intensity = condition_of(code)
    is_day = bool(current.get("is_day", 1))
    sunrise = (daily.get("sunrise") or [None])[0]
    sunset = (daily.get("sunset") or [None])[0]
    wind, gusts = _number(current.get("wind_speed_10m")), _number(current.get("wind_gusts_10m"))
    windy = (wind or 0) >= WINDY_KMH or (gusts or 0) >= GUSTY_KMH
    if condition in WET + SNOWY and intensity is None:
        intensity = "moderate"
    condition = refine(condition, current, windy)
    return Weather(
        condition=condition,
        intensity=intensity,
        code=code,
        is_day=is_day,
        phase=phase_of(_moment(current.get("time")), _moment(sunrise), _moment(sunset), is_day),
        temperature=_number(current.get("temperature_2m")),
        feels_like=_number(current.get("apparent_temperature")),
        humidity=_number(current.get("relative_humidity_2m")),
        cloud_cover=_number(current.get("cloud_cover")),
        precipitation=_number(current.get("precipitation")),
        wind_speed=wind,
        wind_gusts=gusts,
        wind_direction=_number(current.get("wind_direction_10m")),
        windy=windy,
        visibility=_number(current.get("visibility")),
        local_time=str(current["time"]) if current.get("time") else None,
        sunrise=str(sunrise) if sunrise else None,
        sunset=str(sunset) if sunset else None,
        timezone=answer.get("timezone"),
    )


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
            lat = await config.get("ui.weather.latitude", user_id=user_id)
            lon = (await config.get("ui.weather.longitude", user_id=user_id)).value
            name = (await config.get("ui.weather.place", user_id=user_id)).value
        except Exception:
            return None
        if lat.value is None or lon is None:
            return None
        own = user_id is not None and getattr(lat, "source", None) == "user"
        return Place(float(lat.value), float(lon), str(name) if name else None, own)

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
            "current": CURRENT,
            "daily": "sunrise,sunset",
            "forecast_days": 1,
            "timezone": "auto",  # the place's own clock: its dawn, its dusk
            "wind_speed_unit": "kmh",
        }
        try:
            response = await self._get(URL, params)
            response.raise_for_status()
            return replace(read_weather(response.json()), fetched_at=datetime.now(UTC).isoformat())
        except Exception as exc:
            log.warning("weather unavailable", extra={"fields": {"error": type(exc).__name__}})
            return None

    async def places(self, query: str, language: str = "en") -> list[Found]:
        """#70: places matching a name (a town, a city), for a member to pick theirs."""
        query = query.strip()
        if len(query) < 2:
            return []
        try:
            response = await self._get(
                GEOCODING_URL, {"name": query[:80], "count": 8, "language": language, "format": "json"}
            )
            response.raise_for_status()
            found = response.json().get("results") or []
        except Exception as exc:
            log.warning("place search unavailable", extra={"fields": {"error": type(exc).__name__}})
            return []
        places: list[Found] = []
        for row in found:
            try:
                name = str(row["name"])
                region = str(row["admin1"]) if row.get("admin1") and row["admin1"] != name else None
                country = str(row["country"]) if row.get("country") else None
                label = ", ".join(dict.fromkeys(p for p in (name, region, country) if p))
                population = row.get("population")
                places.append(
                    Found(
                        float(row["latitude"]),
                        float(row["longitude"]),
                        name,
                        label,
                        region,
                        country,
                        str(row["country_code"]).upper() if row.get("country_code") else None,
                        int(population) if isinstance(population, int) else None,
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return places
