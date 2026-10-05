import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { usePreferences } from "../../design-system/a11y/PreferencesProvider";
import {
  AMBIENTS,
  type Ambient,
  CELEBRATION_KEYS,
  type CelebrationKey,
} from "../../design-system/a11y/preferences";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useCelebrate } from "../../design-system/feedback/Celebration";
import { AmbientLayer } from "../../design-system/themes/AmbientLayer";
import { useTheme } from "../../design-system/themes/ThemeProvider";
import { useT } from "../../i18n/hooks/useT";
import { InShop } from "./InShop";

/**
 * Ambient animation and celebration (027): the animated layer behind the portal (snow, code rain, bats,
 * disco lights…) and the effect played for rewards — the theme's own, none, or one the member bought (how
 * many more the shop sells is said in one line). Each ambient is previewed live; « Try it » plays it.
 */
interface Choice {
  key: string;
  locked: boolean;
}

export function UniverseLooks() {
  const t = useT();
  const celebrate = useCelebrate();
  const { preferences, setPreference } = usePreferences();
  const { effective, looks } = useTheme();
  const catalog = useQuery({
    queryKey: ["ui", "notification-looks"],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/ui/notification-looks")).data as unknown as {
        ambients?: Choice[];
        celebrations?: Choice[];
      },
  });
  const locked = (list: Choice[] | undefined, key: string) =>
    Boolean(list?.find((c) => c.key === key)?.locked);
  const themeAmbient = effective.theme.background?.ambient ?? "none";
  const tryIt = () => celebrate({ kind: "reward", text: "+40 XP" });
  const ambients = (["theme", ...AMBIENTS] as const).filter(
    (key) => key === "theme" || !locked(catalog.data?.ambients, key),
  );
  const celebrations = (["theme", ...CELEBRATION_KEYS] as const).filter(
    (key) => key === "theme" || !locked(catalog.data?.celebrations, key),
  );
  const lockedCount = (list: Choice[] | undefined) => (list ?? []).filter((c) => c.locked).length;
  return (
    <section className="looks appearance-card" aria-labelledby="universe-looks">
      <h3 id="universe-looks">{t("notifications:universe.title")}</h3>
      <p className="ds-page-header__context">{t("notifications:universe.hint")}</p>
      <fieldset className="ambient-picker">
        <legend>{t("notifications:universe.ambient")}</legend>
        {ambients.map((key) => {
          const current = preferences.ambient === key;
          const shown = (key === "theme" ? themeAmbient : key) as Ambient;
          return (
            <label key={key} className="ambient-picker__item" data-current={current || undefined}>
              <input
                type="radio"
                name="ambient"
                value={key}
                checked={current}
                onChange={() => setPreference("ambient", key as Ambient | "theme")}
              />
              <span className="ambient-picker__preview" aria-hidden="true">
                <AmbientLayer kind={shown} contained />
              </span>
              <span className="looks__name">
                {key === "theme"
                  ? t("notifications:universe.followTheme")
                  : t(`notifications:universe.ambients.${key}`)}
              </span>
            </label>
          );
        })}
      </fieldset>
      <InShop count={lockedCount(catalog.data?.ambients)} type="ambient" />
      <fieldset className="looks__animations">
        <legend>{t("notifications:universe.celebration")}</legend>
        {celebrations.map((key) => {
          const current = preferences.celebration === key;
          return (
            <label key={key} className="looks__chip" data-current={current || undefined}>
              <input
                type="radio"
                name="celebration"
                value={key}
                checked={current}
                onChange={() => {
                  setPreference("celebration", key as CelebrationKey | "theme");
                  setTimeout(tryIt, 80);
                }}
              />
              <Icon name="party" size={14} />
              {key === "theme"
                ? t("notifications:universe.followTheme")
                : t(`notifications:universe.celebrations.${key}`)}
            </label>
          );
        })}
      </fieldset>
      <p className="looks__more">
        <Button variant="secondary" onClick={tryIt}>
          <Icon name="sparkles" size={16} />
          {t("notifications:looks.try")} · {t(`notifications:universe.celebrations.${looks.celebration}`)}
        </Button>
      </p>
      <InShop count={lockedCount(catalog.data?.celebrations)} type="effect" />
    </section>
  );
}
