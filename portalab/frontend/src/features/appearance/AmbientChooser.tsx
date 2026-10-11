import { useCallback, useMemo, useState } from "react";
import { usePreferences } from "../../design-system/a11y/PreferencesProvider";
import type { Ambient } from "../../design-system/a11y/preferences";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { Dialog } from "../../design-system/components/Overlays";
import { AmbientLayer } from "../../design-system/themes/AmbientLayer";
import { useT } from "../../i18n/hooks/useT";
import { HdTag, isHdAmbient } from "./Rarity";
import { WeatherPlace } from "./WeatherPlace";

/**
 * #71: the ambiences a member may wear, as a plain list — no animation runs in it (dozens of live previews
 * slowed the page down). Each shows its name and its rarity, first the rarest; « Preview » opens it in a
 * window — playing, with its details — and « Apply » wears it at once, there or from the list.
 */
export interface AmbientChoice {
  key: string;
  locked: boolean;
  rarity?: string | null;
  price?: number | null;
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
    const owned = choices.filter((c) => !c.locked).map((c) => c.key);
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
            <li key={key} className="ambient-row" data-rarity={rarity} data-current={active || undefined}>
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
                  <span className="ambient-row__preview">
                    <Icon name="eye" size={14} />
                    {t("notifications:universe.preview")}
                  </span>
                </span>
              </button>
              {active ? (
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
      {current === "weather" ? (
        <section className="ambient-chooser__weather" aria-label={t("notifications:universe.weather.title")}>
          <h4>{t("notifications:universe.weather.title")}</h4>
          <WeatherPlace />
        </section>
      ) : null}
      <Dialog
        trigger={<span hidden />}
        open={open !== null}
        onOpenChange={(next) => {
          if (!next) setOpen(null);
        }}
        title={open ? name(open) : ""}
        closeLabel={t("notifications:universe.close")}
        size="lg"
        footer={
          open && current !== open ? (
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
              <AmbientLayer kind={openedKind as Ambient} contained />
            </div>
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
            {openedKind === "weather" ? <WeatherPlace /> : null}
          </div>
        ) : null}
      </Dialog>
    </div>
  );
}
