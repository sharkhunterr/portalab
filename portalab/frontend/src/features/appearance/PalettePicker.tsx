import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../../api/client";
import { usePreferences } from "../../design-system/a11y/PreferencesProvider";
import { PALETTE_KEYS, type PaletteKey } from "../../design-system/a11y/preferences";
import { Icon } from "../../design-system/components/Icon";
import { paletteFor } from "../../design-system/themes/palettes";
import { useTheme } from "../../design-system/themes/ThemeProvider";
import { useT } from "../../i18n/hooks/useT";

/**
 * Colour palettes (027): accent colours over any theme, chosen with swatches; those sold in the shop are
 * locked with a link to buy them. « Theme » keeps the theme's own accents.
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
        palettes?: Array<{ key: string; locked: boolean }>;
      },
  });
  const locked = (key: string) => Boolean(looks.data?.palettes?.find((p) => p.key === key)?.locked);
  return (
    <section className="looks" aria-labelledby="palette-picker">
      <h3 id="palette-picker">{t("notifications:palette.title")}</h3>
      <p className="ds-page-header__context">{t("notifications:palette.hint")}</p>
      <fieldset className="palettes">
        <legend className="visually-hidden">{t("notifications:palette.title")}</legend>
        {PALETTE_KEYS.map((key) => {
          const colors = paletteFor(key, scheme);
          const isLocked = locked(key);
          const current = preferences.palette === key;
          return (
            <label
              key={key}
              className="palettes__item"
              data-current={current || undefined}
              data-locked={isLocked || undefined}
            >
              <input
                type="radio"
                name="palette"
                value={key}
                checked={current}
                disabled={isLocked}
                onChange={() => setPreference("palette", key as PaletteKey)}
              />
              <span className="palettes__swatch" aria-hidden="true">
                <span style={{ background: colors?.accent ?? "var(--color-accent)" }} />
                <span style={{ background: colors?.accentAlt ?? "var(--color-accent-alt)" }} />
              </span>
              <span className="looks__name">
                {t(`notifications:palette.names.${key}`)}
                {isLocked ? <Icon name="lock" size={14} /> : null}
              </span>
              {isLocked ? (
                <Link className="looks__shop" to="/marketplace">
                  {t("notifications:looks.inShop")}
                </Link>
              ) : null}
            </label>
          );
        })}
      </fieldset>
    </section>
  );
}
