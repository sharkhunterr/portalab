import { useCallback, useMemo, useState } from "react";
import { usePreferences } from "../../design-system/a11y/PreferencesProvider";
import type { Ambient } from "../../design-system/a11y/preferences";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { Dialog } from "../../design-system/components/Overlays";
import { AmbientLayer } from "../../design-system/themes/AmbientLayer";
import { WeatherAmbient } from "../../design-system/themes/premium/WeatherAmbient";
import { CONDITIONS, type WeatherReport } from "../../design-system/themes/premium/weatherScene";
import { useT } from "../../i18n/hooks/useT";
import { HdTag, isHdAmbient } from "./Rarity";
import { placeParts, useWeather, WeatherPlace, weatherIcon } from "./WeatherPlace";
import { type Waiting, WaitingTag } from "./waiting";

/**
 * #71: the ambiences a member may wear, as a plain list — no animation runs in it (dozens of live previews
 * slowed the page down). Each shows its name and its rarity, first the rarest; « Preview » opens it in a
 * window — playing, with its details — and « Apply » wears it at once, there or from the list. #88: « live
 * weather » shows the sky it follows on its row, and its settings button opens the window where the place is
 * chosen and every weather can be previewed.
 */
export interface AmbientChoice {
  key: string;
  locked: boolean;
  rarity?: string | null;
  price?: number | null;
  /** #99: won but not wearable yet — what it waits for */
  waiting?: Waiting | null;
}

const RARITY_ORDER = ["legendary", "epic", "rare", "common"] as const;
type Filter = "all" | (typeof RARITY_ORDER)[number] | "free";

function rarityOf(choice: AmbientChoice | undefined): string {
  return choice?.rarity ?? "free";
}

export function AmbientChooser({
  choices,
  themeAmbient,
}: {
  choices: AmbientChoice[];
  /** what « follow the theme » shows */
  themeAmbient: string;
}) {
  const t = useT();
  const { preferences, setPreference } = usePreferences();
  const [filter, setFilter] = useState<Filter>("all");
  const [open, setOpen] = useState<string | null>(null);
  const [sky, setSky] = useState<WeatherReport | null>(null); // #88: a weather previewed in the window
  const byKey = useMemo(() => new Map(choices.map((c) => [c.key, c])), [choices]);
  const name = useCallback(
    (key: string) =>
      key === "theme" ? t("notifications:universe.followTheme") : t(`notifications:universe.ambients.${key}`),
    [t],
  );

  const listed = useMemo(() => {
    const rank = (key: string) => {
      const rarity = rarityOf(byKey.get(key));
      const at = RARITY_ORDER.indexOf(rarity as (typeof RARITY_ORDER)[number]);
      return at < 0 ? RARITY_ORDER.length : at;
    };
    // #99: those won but waiting for a level show too, locked (they can still be previewed)
    const owned = choices.filter((c) => !c.locked || c.waiting).map((c) => c.key);
    owned.sort((a, b) => rank(a) - rank(b) || name(a).localeCompare(name(b)));
    return ["theme", ...owned];
  }, [choices, byKey, name]);
  const counts = useMemo(() => {
    const count: Record<string, number> = {};
    for (const key of listed) {
      if (key === "theme") continue;
      const rarity = rarityOf(byKey.get(key));
      count[rarity] = (count[rarity] ?? 0) + 1;
    }
    return count;
  }, [listed, byKey]);
  const shown = listed.filter(
    (key) => filter === "all" || (key !== "theme" && rarityOf(byKey.get(key)) === filter),
  );

  const apply = (key: string) => setPreference("ambient", key as Ambient | "theme");
  const current = preferences.ambient;
  const opened = open ? byKey.get(open) : undefined;
  const openedKind = open === "theme" ? themeAmbient : (open ?? "none");

  return (
    <div className="ambient-chooser">
      <div className="ambient-chooser__head">
        <h4>{t("notifications:universe.ambient")}</h4>
        <fieldset className="ambient-chooser__filters">
          <legend className="visually-hidden">{t("notifications:universe.filter")}</legend>
          {(["all", ...RARITY_ORDER, "free"] as const)
            .filter((f) => f === "all" || counts[f])
            .map((f) => (
              <button
                key={f}
                type="button"
                className="ambient-chooser__filter"
                data-rarity={f === "all" ? undefined : f}
                aria-pressed={filter === f}
                onClick={() => setFilter(f)}
              >
                {f === "all" ? t("notifications:universe.all") : t(`notifications:universe.rarity.${f}`)}
                {f === "all" ? null : <span className="ambient-chooser__count">{counts[f]}</span>}
              </button>
            ))}
        </fieldset>
      </div>
      <ul className="ambient-chooser__list">
        {shown.map((key) => {
          const choice = byKey.get(key);
          const rarity = key === "theme" ? "theme" : rarityOf(choice);
          const active = current === key;
          return (
            <li
              key={key}
              className="ambient-row"
              data-rarity={rarity}
              data-current={active || undefined}
              data-waiting={choice?.waiting ? "true" : undefined}
            >
              <span className="ambient-row__gem" aria-hidden="true">
                <Icon name={key === "theme" ? "palette" : isHdAmbient(key) ? "gem" : "sparkle"} size={16} />
              </span>
              {/* the name opens the preview window: a large target, the ambience playing there only */}
              <button type="button" className="ambient-row__open" onClick={() => setOpen(key)}>
                <span className="ambient-row__name">{name(key)}</span>
                <span className="ambient-row__meta">
                  <span className="ambient-row__rarity">
                    {key === "theme"
                      ? t(`notifications:universe.ambients.${themeAmbient || "none"}`)
                      : t(`notifications:universe.rarity.${rarity}`)}
                  </span>
                  {isHdAmbient(key) ? <HdTag /> : null}
                  {key === "weather" ? (
                    <WeatherSummary />
                  ) : (
                    <span className="ambient-row__preview">
                      <Icon name="eye" size={14} />
                      {t("notifications:universe.preview")}
                    </span>
                  )}
                </span>
              </button>
              {key === "weather" ? (
                <Button
                  variant="ghost"
                  size="icon"
                  className="ambient-row__settings"
                  aria-label={t("notifications:universe.weather.settings")}
                  title={t("notifications:universe.weather.settings")}
                  onClick={() => setOpen(key)}
                >
                  <Icon name="settings" size={18} />
                </Button>
              ) : null}
              {choice?.waiting ? (
                <WaitingTag waiting={choice.waiting} />
              ) : active ? (
                <span className="ambient-row__active">
                  <Icon name="check" size={14} />
                  {t("notifications:universe.active")}
                </span>
              ) : (
                <Button variant="secondary" className="ambient-row__apply" onClick={() => apply(key)}>
                  {t("notifications:universe.apply")}
                </Button>
              )}
            </li>
          );
        })}
      </ul>
      <Dialog
        trigger={<span hidden />}
        open={open !== null}
        onOpenChange={(next) => {
          if (!next) {
            setOpen(null);
            setSky(null);
          }
        }}
        title={open ? name(open) : ""}
        closeLabel={t("notifications:universe.close")}
        size="lg"
        footer={
          opened?.waiting ? (
            <WaitingTag waiting={opened.waiting} />
          ) : open && current !== open ? (
            <Button
              onClick={() => {
                apply(open);
                setOpen(null);
              }}
            >
              <Icon name="check" size={16} />
              {t("notifications:universe.apply")}
            </Button>
          ) : open ? (
            <span className="ambient-row__active">
              <Icon name="check" size={14} />
              {t("notifications:universe.active")}
            </span>
          ) : null
        }
      >
        {open ? (
          <div className="ambient-detail" data-rarity={open === "theme" ? "theme" : rarityOf(opened)}>
            <div className="ambient-detail__stage">
              {openedKind === "weather" ? (
                <WeatherAmbient
                  contained
                  report={sky ?? undefined}
                  fallback={(kind) => <AmbientLayer kind={kind as Ambient} contained />}
                />
              ) : (
                <AmbientLayer kind={openedKind as Ambient} contained />
              )}
            </div>
            {openedKind === "weather" ? (
              <>
                <WeatherSkies sky={sky} onSky={setSky} />
                <WeatherPlace />
              </>
            ) : null}
            <div className="ambient-detail__facts">
              <span className="ambient-detail__tags">
                <span className="ambient-detail__rarity">
                  <Icon name={open === "theme" ? "palette" : "gem"} size={16} />
                  {open === "theme"
                    ? t("notifications:universe.followTheme")
                    : t(`notifications:universe.rarity.${rarityOf(opened)}`)}
                </span>
                {isHdAmbient(openedKind) ? <HdTag large /> : null}
              </span>
              <p>
                {isHdAmbient(openedKind)
                  ? t("notifications:universe.kind.premium")
                  : t("notifications:universe.kind.light")}
              </p>
              <p>
                {open === "theme"
                  ? t("notifications:universe.origin.theme", { name: name(themeAmbient) })
                  : opened?.rarity
                    ? typeof opened.price === "number"
                      ? t("notifications:universe.origin.owned", { price: opened.price })
                      : t("notifications:universe.origin.ownedGift")
                    : t("notifications:universe.origin.free")}
              </p>
              <p className="ambient-detail__note">{t("notifications:universe.motionNote")}</p>
            </div>
          </div>
        ) : null}
      </Dialog>
    </div>
  );
}

/** #88: on the « live weather » row, the sky it follows now — its icon, the temperature, the town. */
function WeatherSummary() {
  const t = useT();
  const weather = useWeather().data;
  if (!weather?.place) {
    return <span className="ambient-row__preview">{t("notifications:universe.weather.noPlace")}</span>;
  }
  const [town] = placeParts(weather.place.name);
  return (
    <span className="ambient-row__weather">
      <Icon name={weatherIcon(weather)} size={14} />
      {typeof weather.temperature === "number" ? `${Math.round(weather.temperature)}° · ` : null}
      {town}
    </span>
  );
}

const PHASES = ["dawn", "day", "dusk", "night"] as const;

/** #88: every weather the ambience draws, to see each one in the window (the live sky by default). */
function WeatherSkies({
  sky,
  onSky,
}: {
  sky: WeatherReport | null;
  onSky: (sky: WeatherReport | null) => void;
}) {
  const t = useT();
  const phase = sky?.phase ?? "day";
  const pick = (condition: string, at: string = phase) =>
    onSky({
      condition,
      phase: at,
      is_day: at !== "night",
      intensity: "moderate",
    });
  return (
    <fieldset className="weather-skies">
      <legend>{t("notifications:universe.weather.previewAll")}</legend>
      <div className="weather-skies__row">
        <button
          type="button"
          className="weather-skies__chip"
          aria-pressed={sky === null}
          onClick={() => onSky(null)}
        >
          <Icon name="map-pin" size={14} />
          {t("notifications:universe.weather.live")}
        </button>
        {CONDITIONS.map((condition) => (
          <button
            key={condition}
            type="button"
            className="weather-skies__chip"
            aria-pressed={sky?.condition === condition}
            onClick={() => pick(condition)}
          >
            <Icon name={weatherIcon({ condition, phase, is_day: phase !== "night" })} size={14} />
            {t(`notifications:universe.weather.sky.${condition}`)}
          </button>
        ))}
      </div>
      {sky ? (
        <fieldset className="weather-skies__row">
          <legend className="visually-hidden">{t("notifications:universe.weather.hour")}</legend>
          {PHASES.map((at) => (
            <button
              key={at}
              type="button"
              className="weather-skies__chip"
              aria-pressed={phase === at}
              onClick={() => pick(sky.condition ?? "clear", at)}
            >
              <Icon
                name={at === "dawn" ? "sunrise" : at === "dusk" ? "sunset" : at === "night" ? "moon" : "sun"}
                size={14}
              />
              {t(`notifications:universe.weather.phase.${at}`)}
            </button>
          ))}
        </fieldset>
      ) : null}
      <p className="weather-place__note">
        {sky ? t("notifications:universe.weather.previewNote") : t("notifications:universe.weather.liveNote")}
      </p>
    </fieldset>
  );
}
