import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type KeyboardEvent, useContext, useEffect, useId, useState } from "react";
import { IntlContext } from "react-intl";
import { api } from "../../api/client";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { WEATHER_PLACE_CHANGED } from "../../design-system/themes/premium/WeatherAmbient";
import type { WeatherReport } from "../../design-system/themes/premium/weatherScene";
import { useT } from "../../i18n/hooks/useT";

/**
 * #70, #88: where a member's « live weather » comes from, and what it says there — the place saved (their
 * own, or the portal's default) with the sky the forecast gives now (the weather, its intensity, the
 * temperature and how it feels, the wind, the clouds, the local hour, sunrise and sunset); another place
 * found as they type (the town, its region and country, how many live there), or the device's position
 * (rounded to about a kilometre). Saved as their own ``ui.weather.*`` preferences; the ambience follows.
 */
interface Place {
  name?: string | null;
  latitude: number;
  longitude: number;
  own?: boolean;
}
interface Found {
  name: string;
  label: string;
  latitude: number;
  longitude: number;
  region?: string | null;
  country?: string | null;
  country_code?: string | null;
  population?: number | null;
}
export type Weather = WeatherReport & {
  code?: number | null;
  feels_like?: number | null;
  humidity?: number | null;
  local_time?: string | null;
  sunrise?: string | null;
  sunset?: string | null;
  fetched_at?: string | null;
  refresh_minutes?: number | null;
  place?: Place | null;
};

export const WEATHER_QUERY = ["ui", "weather"] as const;

export function useWeather() {
  return useQuery({
    queryKey: WEATHER_QUERY,
    retry: false,
    staleTime: 5 * 60 * 1000,
    queryFn: async () => (await api.GET("/api/v1/ui/weather")).data as unknown as Weather,
  });
}

/** The icon of a sky: the sun or the moon showing through, what falls. */
export function weatherIcon(weather: Weather | null | undefined): string {
  const night = weather?.phase === "night" || weather?.is_day === false;
  switch (weather?.condition) {
    case "clear":
      return weather.phase === "dawn"
        ? "sunrise"
        : weather.phase === "dusk"
          ? "sunset"
          : night
            ? "moon"
            : "sun";
    case "mainly_clear":
    case "partly_cloudy":
    case "hazy":
      return night ? "cloud-moon" : "cloud-sun";
    case "windy":
      return "wind";
    case "mist":
      return "cloud-fog";
    case "sleet":
      return "cloud-snow";
    case "overcast":
      return "cloudy";
    case "fog":
    case "rime_fog":
      return "cloud-fog";
    case "drizzle":
    case "freezing_drizzle":
      return "cloud-drizzle";
    case "rain":
    case "freezing_rain":
      return "rain";
    case "showers":
      return night ? "cloud-moon-rain" : "cloud-sun-rain";
    case "snow":
    case "snow_grains":
    case "snow_showers":
      return "cloud-snow";
    case "storm":
      return "lightning";
    case "storm_hail":
      return "cloud-hail";
    default:
      return "cloud";
  }
}

/** « Saint-Leu-la-Forêt » and « Île-de-France, France », from the saved « Saint-Leu-la-Forêt, Île-de-France, France ». */
export function placeParts(name: string | null | undefined): [string, string | null] {
  const [first, ...rest] = (name ?? "").split(", ");
  return [first ?? "", rest.length ? rest.join(", ") : null];
}

function flag(code: string | null | undefined): string {
  if (!code || !/^[A-Z]{2}$/.test(code)) return "";
  return String.fromCodePoint(...[...code].map((c) => 0x1f1a5 + c.charCodeAt(0)));
}

const hour = (iso: string | null | undefined) => (iso ? iso.slice(11, 16) : "");

async function savePlace(place: Place | null) {
  await api.PUT("/api/v1/me/preferences", {
    body: {
      "ui.weather.latitude": place ? place.latitude : null,
      "ui.weather.longitude": place ? place.longitude : null,
      "ui.weather.place": place?.name ?? null,
    } as never,
  });
  window.dispatchEvent(new Event(WEATHER_PLACE_CHANGED));
}

/** The sky now over the saved place. */
export function WeatherNow({ weather }: { weather: Weather | undefined }) {
  const t = useT();
  const locale = useContext(IntlContext)?.locale ?? "en";
  const place = weather?.place;
  const [town, region] = placeParts(place?.name);
  const number = (n: number, digits = 0) =>
    new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(n);
  if (!place) {
    return (
      <div className="weather-now" data-empty>
        <Icon name="map" size={20} />
        <p>{t("notifications:universe.weather.none")}</p>
      </div>
    );
  }
  const has = (n: number | null | undefined): n is number => typeof n === "number";
  const facts = [
    has(weather?.feels_like)
      ? {
          icon: "thermometer",
          text: t("notifications:universe.weather.feelsLike", { value: number(weather.feels_like) }),
        }
      : null,
    has(weather?.wind_speed)
      ? {
          icon: "wind",
          text: has(weather.wind_gusts)
            ? t("notifications:universe.weather.windGusts", {
                speed: number(weather.wind_speed),
                gusts: number(weather.wind_gusts),
              })
            : t("notifications:universe.weather.wind", { speed: number(weather.wind_speed) }),
        }
      : null,
    has(weather?.cloud_cover)
      ? {
          icon: "cloud",
          text: t("notifications:universe.weather.clouds", { value: number(weather.cloud_cover) }),
        }
      : null,
    has(weather?.humidity)
      ? {
          icon: "droplets",
          text: t("notifications:universe.weather.humidity", { value: number(weather.humidity) }),
        }
      : null,
    has(weather?.precipitation) && weather.precipitation > 0
      ? {
          icon: "umbrella",
          text: t("notifications:universe.weather.precipitation", {
            value: number(weather.precipitation, 1),
          }),
        }
      : null,
  ].filter((f): f is { icon: string; text: string } => f !== null);
  return (
    <div className="weather-now" data-phase={weather?.phase ?? undefined}>
      <div className="weather-now__sky">
        <span className="weather-now__icon" aria-hidden="true">
          <Icon name={weatherIcon(weather)} size={40} />
        </span>
        {has(weather?.temperature) ? (
          <span className="weather-now__temp">{number(weather.temperature)}°</span>
        ) : null}
        <span className="weather-now__what">
          <strong>
            {weather?.condition
              ? t(`notifications:universe.weather.sky.${weather.condition}`)
              : t("notifications:universe.weather.unavailable")}
          </strong>
          <span className="weather-now__tags">
            {weather?.intensity ? (
              <span className="weather-now__tag">
                {t(`notifications:universe.weather.intensity.${weather.intensity}`)}
              </span>
            ) : null}
            {weather?.phase ? (
              <span className="weather-now__tag">
                {t(`notifications:universe.weather.phase.${weather.phase}`)}
              </span>
            ) : null}
            {weather?.windy ? (
              <span className="weather-now__tag">{t("notifications:universe.weather.windy")}</span>
            ) : null}
          </span>
        </span>
      </div>
      {facts.length ? (
        <ul className="weather-now__facts">
          {facts.map((fact) => (
            <li key={fact.icon}>
              <Icon name={fact.icon} size={14} />
              {fact.text}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="weather-now__place">
        <Icon name="map-pin" size={18} />
        <span>
          <strong>{town || `${place.latitude}, ${place.longitude}`}</strong>
          <span className="weather-now__where">
            {[
              region,
              place.own
                ? t("notifications:universe.weather.own")
                : t("notifications:universe.weather.portal"),
            ]
              .filter(Boolean)
              .join(" · ")}
          </span>
          {weather?.local_time ? (
            <span className="weather-now__where">
              {[
                t("notifications:universe.weather.localTime", { time: hour(weather.local_time) }),
                weather.sunrise && weather.sunset
                  ? t("notifications:universe.weather.sun", {
                      sunrise: hour(weather.sunrise),
                      sunset: hour(weather.sunset),
                    })
                  : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </span>
          ) : null}
        </span>
      </div>
      {weather?.fetched_at ? (
        // when the sky was last asked for, and how often it is asked again
        <p className="weather-now__fresh">
          <Icon name="sync" size={13} />
          {t("notifications:universe.weather.refreshed", {
            time: new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit" }).format(
              new Date(weather.fetched_at),
            ),
            minutes: weather.refresh_minutes ?? 15,
          })}
        </p>
      ) : null}
    </div>
  );
}

export function WeatherPlace() {
  const t = useT();
  const intl = useContext(IntlContext);
  const language = (intl?.locale ?? "en").slice(0, 2);
  const queryClient = useQueryClient();
  const listId = useId();
  const [query, setQuery] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "denied" | "saved">("idle");
  const current = useWeather();
  const wanted = query.trim();
  // the places come as the member types (a short pause first: one question per word, not per letter)
  const [asked, setAsked] = useState("");
  useEffect(() => {
    const timer = window.setTimeout(() => setAsked(wanted), 350);
    return () => window.clearTimeout(timer);
  }, [wanted]);
  const found = useQuery({
    queryKey: ["ui", "weather", "places", asked, language],
    enabled: asked.length >= 2,
    staleTime: 10 * 60 * 1000,
    queryFn: async () =>
      ((
        await api.GET("/api/v1/ui/weather/places", {
          params: { query: { q: asked, language } },
        })
      ).data ?? []) as unknown as Found[],
  });

  const choose = async (place: Place | null) => {
    setState("busy");
    await savePlace(place);
    setQuery("");
    setAsked("");
    await queryClient.invalidateQueries({ queryKey: WEATHER_QUERY });
    setState("saved");
  };

  const here = () => {
    if (!navigator.geolocation) return setState("denied");
    setState("busy");
    navigator.geolocation.getCurrentPosition(
      (position) =>
        void choose({
          // about a kilometre: enough for the sky, no more of where the member is
          latitude: Math.round(position.coords.latitude * 100) / 100,
          longitude: Math.round(position.coords.longitude * 100) / 100,
          name: t("notifications:universe.weather.myPosition"),
        }),
      () => setState("denied"),
      { maximumAge: 60 * 60 * 1000, timeout: 15000 },
    );
  };

  const first = (event: KeyboardEvent<HTMLInputElement>) => {
    const results = found.data ?? [];
    if (event.key === "Enter") {
      event.preventDefault();
      if (results.length === 1 && results[0]) void choose({ ...results[0], name: results[0].label });
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      document.querySelector<HTMLButtonElement>(`[id="${listId}"] button`)?.focus();
    }
  };
  const move = (event: KeyboardEvent<HTMLButtonElement>) => {
    const item = event.currentTarget.closest("li");
    const to =
      event.key === "ArrowDown"
        ? item?.nextElementSibling
        : event.key === "ArrowUp"
          ? item?.previousElementSibling
          : null;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      to?.querySelector("button")?.focus();
    }
  };

  const results = asked.length >= 2 && asked === wanted ? found.data : undefined;
  const searching = wanted.length >= 2 && (wanted !== asked || found.isFetching);
  const own = Boolean(current.data?.place?.own);
  const people = (n: number) =>
    new Intl.NumberFormat(intl?.locale ?? "en", { notation: "compact" }).format(n);
  return (
    <div className="weather-place">
      <WeatherNow weather={current.data} />
      <section className="weather-place__change" aria-labelledby={`${listId}-title`}>
        <h5 id={`${listId}-title`}>{t("notifications:universe.weather.change")}</h5>
        <label className="weather-place__search">
          <Icon name={searching ? "spinner" : "search"} size={16} />
          <span className="visually-hidden">{t("notifications:universe.weather.search")}</span>
          <input
            type="search"
            value={query}
            maxLength={80}
            autoComplete="off"
            placeholder={t("notifications:universe.weather.search")}
            aria-controls={listId}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={first}
          />
        </label>
        {results ? (
          results.length ? (
            <ul
              className="weather-place__found"
              id={listId}
              aria-label={t("notifications:universe.weather.results")}
            >
              {results.map((p) => (
                <li key={`${p.latitude},${p.longitude}`}>
                  <button
                    type="button"
                    onClick={() => void choose({ ...p, name: p.label })}
                    onKeyDown={move}
                    disabled={state === "busy"}
                  >
                    <span className="weather-place__flag" aria-hidden="true">
                      {flag(p.country_code) || <Icon name="map-pin" size={16} />}
                    </span>
                    <span className="weather-place__found-text">
                      <strong>{p.name}</strong>
                      <span>{[p.region, p.country].filter(Boolean).join(", ")}</span>
                    </span>
                    {p.population ? (
                      <span className="weather-place__people">
                        {t("notifications:universe.weather.people", { value: people(p.population) })}
                      </span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="weather-place__note">{t("notifications:universe.weather.noResult")}</p>
          )
        ) : (
          <p className="weather-place__note">{t("notifications:universe.weather.searchHint")}</p>
        )}
        <div className="weather-place__actions">
          <Button type="button" variant="secondary" onClick={here} disabled={state === "busy"}>
            <Icon name="locate" size={16} />
            {t("notifications:universe.weather.mine")}
          </Button>
          {own ? (
            <Button
              type="button"
              variant="ghost"
              onClick={() => void choose(null)}
              disabled={state === "busy"}
            >
              <Icon name="undo" size={16} />
              {t("notifications:universe.weather.reset")}
            </Button>
          ) : null}
        </div>
        {state === "denied" ? (
          <p className="weather-place__note" role="alert">
            {t("notifications:universe.weather.denied")}
          </p>
        ) : null}
        {state === "saved" ? (
          <p className="weather-place__note weather-place__note--done" role="status">
            <Icon name="check" size={14} />
            {t("notifications:universe.weather.saved")}
          </p>
        ) : null}
      </section>
    </div>
  );
}
