import { useQuery } from "@tanstack/react-query";
import { type ReactElement, useId } from "react";
import { api } from "../../api/client";
import { usePreferences } from "../../design-system/a11y/PreferencesProvider";
import type { UiPreferences } from "../../design-system/a11y/preferences";
import { CheckboxField, SelectField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { PolicyField, type PolicyState } from "../../design-system/components/PolicyField";
import { DEFAULT_FAMILY } from "../../design-system/themes/builtin";
import { presentationOf, type ThemeDefinition } from "../../design-system/themes/schema";
import { useTheme } from "../../design-system/themes/ThemeProvider";
import { InShop } from "./InShop";
import { LevelBadgePicker } from "./LevelBadgePicker";
import { LevelUpPicker } from "./LevelUpPicker";
import { NotificationLooks } from "./NotificationLooks";
import { PalettePicker } from "./PalettePicker";
import { RarityTag } from "./Rarity";
import { UniverseLooks } from "./UniverseLooks";

/**
 * Appearance & accessibility settings (spec 022): theme, density, text size, contrast, motion, sound and
 * notification appearance. Policy-locked settings explain why; the user's own choice is kept. Changing a
 * setting never changes data — only presentation. Strings externalized for i18n (026).
 */
export const appearanceStrings = {
  title: "Appearance & accessibility",
  gallery: "Themes",
  galleryHint: "A theme can change colors and fonts, but also the layout, the animations and the sounds.",
  current: "Current",
  colorMode: "Light or dark",
  colorModes: { dark: "Dark", light: "Light", system: "Follow my device" },
  layouts: {
    sidebar: "Side menu",
    topbar: "Top bar",
    rail: "Icon rail",
    orbit: "Orbit bubble",
    "bottom-bar": "Bottom bar",
    drawer: "Drawer",
    dock: "Dock",
    tabs: "Book tabs",
    launcher: "Launcher screen",
    terminal: "Command line",
    reel: "Film reel",
    lights: "String of lights",
    vcr: "Video recorder",
    sheet: "Phone sheet",
  } as Record<string, string>,
  footerHeader: "header at the bottom",
  theme: "Theme",
  themeDefault: "Portal default",
  themeFallback: "Your theme is not available right now; the portal default is used.",
  density: "Density",
  densities: { compact: "Compact", comfortable: "Comfortable", spacious: "Spacious" },
  textScale: "Text size",
  contrast: "High contrast",
  reducedMotion: "Reduce motion",
  motions: { system: "Follow my device", on: "On", off: "Off" },
  sound: "Play sounds",
  notificationPosition: "Notification position",
  positions: {
    "top-end": "Top end",
    "top-start": "Top start",
    "bottom-end": "Bottom end",
    "bottom-start": "Bottom start",
  },
  notificationStyle: "Notification style",
  styles: { toast: "Toast", banner: "Banner" },
  campaignThemes: "Show seasonal campaign themes",
  forcedMotion: "Your administrator reduces motion for everyone.",
  display: "Display",
  displayHint: "Light or dark, density, text size and motion: how the portal reads for you.",
  notifications: "Notifications",
} as const;

interface View {
  key: string;
  locked: boolean;
  user_value: unknown;
  user_value_retained: boolean;
}

function usePolicyStates(): (key: string) => { state: PolicyState; retained: string | null } {
  const views = useQuery({
    queryKey: ["me", "preferences", "views"],
    queryFn: async () =>
      ((await api.GET("/api/v1/me/preferences")).data as unknown as { preferences: View[] }).preferences,
    retry: false,
  });
  return (key: string) => {
    const view = views.data?.find((v) => v.key === key);
    if (!view?.locked) return { state: "free", retained: null };
    return { state: "locked", retained: view.user_value_retained ? String(view.user_value) : null };
  };
}

/** How many themes the shop sells that the member does not own yet (027): said in one line, not listed. */
function useShopThemeCount(): number {
  const locked = useQuery({
    queryKey: ["ui", "themes", "locked"],
    retry: false,
    queryFn: async () =>
      ((await api.GET("/api/v1/ui/themes")).data as unknown as { locked?: Array<{ key: string }> }).locked ??
      [],
  });
  return locked.data?.length ?? 0;
}

/** #72: the rarity of each theme the shop sells (by its key and by its family). */
function useThemeRarities(): Map<string, string> {
  const catalog = useQuery({
    queryKey: ["ui", "themes", "rarities"],
    retry: false,
    queryFn: async () =>
      (
        (await api.GET("/api/v1/ui/themes")).data as unknown as {
          themes?: Array<{ key: string; family?: string | null; rarity?: string | null }>;
        }
      ).themes ?? [],
  });
  const rarities = new Map<string, string>();
  for (const theme of catalog.data ?? []) {
    if (!theme.rarity) continue;
    rarities.set(theme.key, theme.rarity);
    if (theme.family) rarities.set(theme.family, theme.rarity);
  }
  return rarities;
}

/** One card per theme family/theme with a miniature of its arrangement (027 T061): never data, only looks. */
function ThemeGallery({
  themes,
  current,
  onChoose,
}: {
  themes: readonly ThemeDefinition[];
  current: string;
  onChoose: (theme: ThemeDefinition) => void;
}) {
  const shown = themes.filter(
    (theme, index) => !theme.family || themes.findIndex((t) => t.family === theme.family) === index,
  );
  const currentTheme = themes.find((t) => t.key === current);
  const rarities = useThemeRarities();
  return (
    <>
      <ul className="theme-gallery__list">
        {shown.map((theme) => {
          const p = presentationOf(theme);
          const active = theme.key === current || (theme.family && theme.family === currentTheme?.family);
          const name =
            theme.family === DEFAULT_FAMILY ? "Portalab" : theme.family ? theme.family : theme.name;
          const layout = `${appearanceStrings.layouts[p.nav.desktop] ?? p.nav.desktop}${
            p.headerPosition === "bottom" ? ` · ${appearanceStrings.footerHeader}` : ""
          }`;
          return (
            <li key={theme.key}>
              <button
                type="button"
                className="theme-card"
                aria-pressed={Boolean(active)}
                data-rarity={
                  rarities.get(theme.key) ?? (theme.family ? rarities.get(theme.family) : undefined)
                }
                onClick={() => onChoose(theme)}
              >
                <RarityTag
                  rarity={rarities.get(theme.key) ?? (theme.family ? rarities.get(theme.family) : undefined)}
                />
                <ThemeMiniature theme={theme} />
                <span className="theme-card__name">
                  {name}
                  {active ? (
                    <span className="theme-card__current">
                      <Icon name="check" size={12} />
                      {appearanceStrings.current}
                    </span>
                  ) : null}
                </span>
                <span className="theme-card__meta">{layout}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </>
  );
}

export function ThemeMiniature({ theme }: { theme: ThemeDefinition }) {
  const p = presentationOf(theme);
  const c = theme.colors;
  const bar = (
    <span className="theme-mini__bar" style={{ background: c.surfaceRaised, borderColor: c.border }} />
  );
  const nav = p.nav.desktop;
  return (
    <span
      className="theme-mini"
      data-nav={nav}
      data-cards={p.cards}
      aria-hidden="true"
      style={{ background: c.surface, color: c.text, borderColor: c.border }}
    >
      {p.headerPosition === "top" ? bar : null}
      {nav === "terminal" ? (
        <span className="theme-mini__terminal" style={{ color: c.accent }}>
          {"> ~/ ▮"}
        </span>
      ) : null}
      <span className="theme-mini__body">
        {nav === "sidebar" || nav === "rail" || nav === "tabs" ? (
          <span
            className="theme-mini__side"
            style={{ background: nav === "tabs" ? c.accent : c.surfaceRaised }}
          />
        ) : null}
        <span className="theme-mini__content">
          {nav === "topbar" ? <span className="theme-mini__tabs" style={{ background: c.accent }} /> : null}
          <span
            className="theme-mini__font"
            style={{
              fontFamily: theme.typography?.headingFamily ?? theme.typography?.fontFamily,
              color: c.text,
            }}
          >
            Aa
          </span>
          <span className="theme-mini__card" style={{ background: c.surfaceRaised, borderColor: c.border }}>
            <span style={{ background: c.accent }} />
          </span>
          <span className="theme-mini__card" style={{ background: c.surfaceRaised, borderColor: c.border }}>
            <span style={{ background: c.accentAlt ?? c.accent }} />
          </span>
        </span>
        {nav === "orbit" ? <span className="theme-mini__orbit" style={{ background: c.accent }} /> : null}
        {nav === "dock" ? (
          <span className="theme-mini__dock" style={{ background: c.surfaceRaised, borderColor: c.border }}>
            <span style={{ background: c.accent }} />
            <span style={{ background: c.textMuted }} />
            <span style={{ background: c.textMuted }} />
          </span>
        ) : null}
        {nav === "launcher" ? (
          <span className="theme-mini__launcher" style={{ background: c.accent }} />
        ) : null}
      </span>
      {p.headerPosition === "bottom" ? bar : null}
    </span>
  );
}

export function AppearanceSettings() {
  const headingId = useId();
  const { preferences, policy, setPreference } = usePreferences();
  const { themes, effective } = useTheme();
  const policyOf = usePolicyStates();
  const shopThemes = useShopThemeCount();
  const set =
    <K extends keyof UiPreferences>(key: K) =>
    (value: UiPreferences[K]) =>
      setPreference(key, value);
  const field = (key: string, render: (disabled: boolean, describedBy?: string) => ReactElement) => {
    const { state, retained } = policyOf(key);
    return (
      <PolicyField id={key} state={state} retainedValue={retained}>
        {({ disabled, describedBy }) => render(disabled, describedBy)}
      </PolicyField>
    );
  };
  return (
    <section aria-labelledby={headingId} className="account-page appearance-page">
      <PageHeader titleId={headingId} level={2} icon="palette" title={appearanceStrings.title} />
      {effective.fallback ? <p role="status">{appearanceStrings.themeFallback}</p> : null}
      <section className="appearance-card" aria-labelledby="theme-gallery">
        <h3 id="theme-gallery">{appearanceStrings.gallery}</h3>
        <p className="ds-page-header__context">{appearanceStrings.galleryHint}</p>
        <ThemeGallery
          themes={themes}
          current={effective.theme.key}
          onChoose={(theme) => {
            set("theme")(theme.family ?? theme.key);
            if (theme.family) set("colorMode")(theme.colorScheme);
          }}
        />
        <div className="appearance-row">
          {field("ui.theme", (disabled, describedBy) => (
            <SelectField
              label={appearanceStrings.theme}
              value={preferences.theme ?? ""}
              disabled={disabled}
              aria-describedby={describedBy}
              onChange={(event) => set("theme")(event.target.value || null)}
            >
              <option value="">{appearanceStrings.themeDefault}</option>
              {themes.map((theme) => (
                <option key={theme.key} value={theme.key}>
                  {theme.name}
                </option>
              ))}
            </SelectField>
          ))}
          {field("ui.colorMode", (disabled) => (
            <SelectField
              label={appearanceStrings.colorMode}
              value={preferences.colorMode}
              disabled={disabled}
              onChange={(event) => set("colorMode")(event.target.value as UiPreferences["colorMode"])}
            >
              {Object.entries(appearanceStrings.colorModes).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </SelectField>
          ))}
        </div>
        <InShop count={shopThemes} type="theme" />
        {field("ui.campaignThemes", (disabled) => (
          <CheckboxField
            label={appearanceStrings.campaignThemes}
            checked={preferences.campaignThemes === "allow"}
            disabled={disabled}
            onChange={(event) => set("campaignThemes")(event.target.checked ? "allow" : "ignore")}
          />
        ))}
      </section>
      <PalettePicker />
      <LevelBadgePicker />
      <LevelUpPicker />
      <section className="appearance-card" aria-labelledby="appearance-display">
        <h3 id="appearance-display">{appearanceStrings.display}</h3>
        <p className="ds-page-header__context">{appearanceStrings.displayHint}</p>
        <div className="appearance-row">
          {field("ui.density", (disabled) => (
            <SelectField
              label={appearanceStrings.density}
              value={preferences.density}
              disabled={disabled}
              onChange={(event) => set("density")(event.target.value as UiPreferences["density"])}
            >
              {Object.entries(appearanceStrings.densities).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </SelectField>
          ))}
          {field("ui.reducedMotion", (disabled) => (
            <SelectField
              label={appearanceStrings.reducedMotion}
              value={preferences.reducedMotion}
              disabled={disabled || policy.forceReducedMotion}
              hint={policy.forceReducedMotion ? appearanceStrings.forcedMotion : undefined}
              onChange={(event) => set("reducedMotion")(event.target.value as UiPreferences["reducedMotion"])}
            >
              {Object.entries(appearanceStrings.motions).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </SelectField>
          ))}
        </div>
        {field("ui.textScale", (disabled) => (
          <div className="ds-field appearance-scale">
            <label htmlFor="ui-text-scale">{appearanceStrings.textScale}</label>
            <span className="appearance-scale__row">
              <span aria-hidden="true">A</span>
              <input
                id="ui-text-scale"
                type="range"
                min={policy.textScaleMin}
                max={policy.textScaleMax}
                step={0.05}
                value={preferences.textScale}
                disabled={disabled}
                aria-valuetext={`${Math.round(preferences.textScale * 100)}%`}
                onChange={(event) => set("textScale")(Number(event.target.value))}
              />
              <span aria-hidden="true" className="appearance-scale__big">
                A
              </span>
              <output htmlFor="ui-text-scale">{Math.round(effective.textScale * 100)}%</output>
            </span>
          </div>
        ))}
        <div className="appearance-toggles">
          {field("ui.contrast", (disabled) => (
            <CheckboxField
              label={appearanceStrings.contrast}
              checked={preferences.contrast === "high"}
              disabled={disabled}
              onChange={(event) => set("contrast")(event.target.checked ? "high" : "default")}
            />
          ))}
          {field("ui.soundEnabled", (disabled) => (
            <CheckboxField
              label={appearanceStrings.sound}
              checked={preferences.soundEnabled}
              disabled={disabled}
              onChange={(event) => set("soundEnabled")(event.target.checked)}
            />
          ))}
        </div>
      </section>
      <UniverseLooks />
      <NotificationLooks
        position={field("ui.notificationPosition", (disabled) => (
          <SelectField
            label={appearanceStrings.notificationPosition}
            value={preferences.notificationPosition}
            disabled={disabled}
            onChange={(event) =>
              set("notificationPosition")(event.target.value as UiPreferences["notificationPosition"])
            }
          >
            {Object.entries(appearanceStrings.positions).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </SelectField>
        ))}
      />
    </section>
  );
}
