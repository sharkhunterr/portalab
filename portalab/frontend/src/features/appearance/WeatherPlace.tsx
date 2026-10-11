import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useContext, useState } from "react";
import { IntlContext } from "react-intl";
import { api } from "../../api/client";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { WEATHER_PLACE_CHANGED } from "../../design-system/themes/premium/WeatherAmbient";
import { useT } from "../../i18n/hooks/useT";

/**
 * #70: where a member's « live weather » comes from — their own place, found by name or taken from the
 * device's position (rounded to about a kilometre), or the portal's default place. Saved as their own
 * ``ui.weather.*`` preferences; the ambience follows at once.
 */
interface Place {
  name?: string | null;
  latitude: number;
  longitude: number;
}

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

export function WeatherPlace() {
  const t = useT();
  const language = (useContext(IntlContext)?.locale ?? "en").slice(0, 2);
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<Place[] | null>(null);
  const [state, setState] = useState<"idle" | "busy" | "denied" | "saved">("idle");
  const current = useQuery({
    queryKey: ["ui", "weather"],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/ui/weather")).data as unknown as {
        condition: string | null;
        temperature?: number | null;
        place?: Place | null;
      },
  });

  const choose = async (place: Place | null) => {
    setState("busy");
    await savePlace(place);
    setFound(null);
    setQuery("");
    await queryClient.invalidateQueries({ queryKey: ["ui", "weather"] });
    setState("saved");
  };

  const search = async (event: FormEvent) => {
    event.preventDefault();
    if (query.trim().length < 2) return;
    setState("busy");
    const answer = await api.GET("/api/v1/ui/weather/places", {
      params: { query: { q: query.trim(), language } },
    });
    setFound((answer.data as Place[] | undefined) ?? []);
    setState("idle");
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

  const place = current.data?.place;
  return (
    <div className="weather-place">
      <p className="weather-place__current">
        <Icon name="map" size={16} />
        {place
          ? t("notifications:universe.weather.current", {
              place: place.name ?? `${place.latitude}, ${place.longitude}`,
            })
          : t("notifications:universe.weather.none")}
        {typeof current.data?.temperature === "number" ? (
          <span className="weather-place__temp">{Math.round(current.data.temperature)}°</span>
        ) : null}
      </p>
      <form className="weather-place__search" onSubmit={search}>
        <label className="visually-hidden" htmlFor="weather-place-query">
          {t("notifications:universe.weather.search")}
        </label>
        <input
          id="weather-place-query"
          type="search"
          value={query}
          minLength={2}
          maxLength={80}
          placeholder={t("notifications:universe.weather.search")}
          onChange={(event) => setQuery(event.target.value)}
        />
        <Button type="submit" variant="secondary" disabled={state === "busy"}>
          <Icon name="search" size={16} />
          {t("notifications:universe.weather.find")}
        </Button>
        <Button type="button" variant="secondary" onClick={here} disabled={state === "busy"}>
          <Icon name="map" size={16} />
          {t("notifications:universe.weather.mine")}
        </Button>
      </form>
      {found ? (
        found.length ? (
          <ul className="weather-place__found">
            {found.map((p) => (
              <li key={`${p.latitude},${p.longitude}`}>
                <button type="button" onClick={() => void choose(p)}>
                  {p.name}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="weather-place__note">{t("notifications:universe.weather.noResult")}</p>
        )
      ) : null}
      {state === "denied" ? (
        <p className="weather-place__note" role="alert">
          {t("notifications:universe.weather.denied")}
        </p>
      ) : null}
      {state === "saved" ? (
        <p className="weather-place__note" role="status">
          {t("notifications:universe.weather.saved")}
        </p>
      ) : null}
      <p className="weather-place__note">
        <button type="button" className="weather-place__reset" onClick={() => void choose(null)}>
          {t("notifications:universe.weather.reset")}
        </button>
      </p>
    </div>
  );
}
