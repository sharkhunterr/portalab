import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { usePreferences } from "../../design-system/a11y/PreferencesProvider";
import type { PaletteKey } from "../../design-system/a11y/preferences";
import { paletteFor } from "../../design-system/themes/palettes";
import { useTheme } from "../../design-system/themes/ThemeProvider";
import { useT } from "../../i18n/hooks/useT";
import { InShop } from "./InShop";
import { RarityTag, rarityIn } from "./Rarity";
import { type Waiting, WaitingTag, waitingIn } from "./waiting";

/**
 * Colour palettes (027): accent colours over any theme, chosen with swatches — only the member's own; how
 * many more the shop sells is said in one line. « Theme » keeps the theme's own accents.
 */
export function PalettePicker() {
  const t = useT();
  const { preferences, setPreference } = usePreferences();
  const { effective } = useTheme();
  const scheme = effective.theme.colorScheme === "light" ? "light" : "dark";
  const looks = useQuery({
    queryKey: ["ui", "notification-looks"],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/ui/notification-looks")).data as unknown as {
        palettes?: Array<{ key: string; locked: boolean; rarity?: string | null; waiting?: Waiting | null }>;
      },
  });
  const locked = (key: string) => Boolean(looks.data?.palettes?.find((p) => p.key === key)?.locked);
  // 028: the palettes are the visual packs' (Portalab's own included): the server lists them — « theme »
  // (the theme's own accents) first
  const keys = (looks.data?.palettes ?? []).map((p) => p.key).filter((key) => key !== "theme");
  const all = ["theme", ...keys];
  // #99: those won but waiting for a level show too, locked
  const owned = all.filter((key) => !locked(key) || waitingIn(looks.data?.palettes, key));
  return (
    <section className="looks appearance-card" aria-labelledby="palette-picker">
      <h3 id="palette-picker">{t("notifications:palette.title")}</h3>
      <p className="ds-page-header__context">{t("notifications:palette.hint")}</p>
      <fieldset className="palettes">
        <legend className="visually-hidden">{t("notifications:palette.title")}</legend>
        {owned.map((key) => {
          const colors = paletteFor(key, scheme);
          const current = preferences.palette === key;
          const waiting = waitingIn(looks.data?.palettes, key);
          return (
            <label
              key={key}
              className="palettes__item"
              data-current={current || undefined}
              data-waiting={waiting ? "true" : undefined}
              data-rarity={rarityIn(looks.data?.palettes, key)}
            >
              <RarityTag rarity={rarityIn(looks.data?.palettes, key)} />
              <input
                type="radio"
                name="palette"
                value={key}
                checked={current}
                disabled={Boolean(waiting)}
                onChange={() => setPreference("palette", key as PaletteKey)}
              />
              <span className="palettes__swatch" aria-hidden="true">
                <span style={{ background: colors?.accent ?? "var(--color-accent)" }} />
                <span style={{ background: colors?.accentAlt ?? "var(--color-accent-alt)" }} />
              </span>
              <span className="looks__name">{t(`notifications:palette.names.${key}`)}</span>
              {waiting ? <WaitingTag waiting={waiting} /> : null}
            </label>
          );
        })}
      </fieldset>
      <InShop count={all.length - owned.length} type="palette" />
    </section>
  );
}
