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
import { useT } from "../../i18n/hooks/useT";
import { InShop } from "./InShop";
import { LevelBadgePicker } from "./LevelBadgePicker";
import { LevelUpPicker } from "./LevelUpPicker";
import { NotificationLooks } from "./NotificationLooks";
import { PalettePicker } from "./PalettePicker";
import { PluginLooks } from "./PluginLooks";
import { RarityTag } from "./Rarity";
import { SafeModeSwitch } from "./SafeModeSwitch";
import { UniverseLooks } from "./UniverseLooks";

/**
 * Appearance & accessibility settings (spec 022): theme, density, text size, contrast, motion, sound and
 * notification appearance. Policy-locked settings explain why; the user's own choice is kept. Changing a
 * setting never changes data — only presentation. Its texts come from the catalogs (issue 240).
 */
/** Issue 240: the page's texts, in the member's language (they were written in English for everyone). */
export function useAppearanceStrings() {
  const t = useT();
  return {
    title: t("notifications:appearance.title"),
    gallery: t("notifications:appearance.gallery"),
    galleryHint: t("notifications:appearance.galleryHint"),
    current: t("notifications:appearance.current"),
    colorMode: t("notifications:appearance.colorMode"),
    colorModes: {
      dark: t("notifications:appearance.colorModes.dark"),
      light: t("notifications:appearance.colorModes.light"),
      system: t("notifications:appearance.colorModes.system"),
    },
    layouts: {
      sidebar: t("notifications:appearance.layouts.sidebar"),
      topbar: t("notifications:appearance.layouts.topbar"),
      rail: t("notifications:appearance.layouts.rail"),
      orbit: t("notifications:appearance.layouts.orbit"),
      "bottom-bar": t("notifications:appearance.layouts.bottom-bar"),
      drawer: t("notifications:appearance.layouts.drawer"),
      dock: t("notifications:appearance.layouts.dock"),
      tabs: t("notifications:appearance.layouts.tabs"),
      launcher: t("notifications:appearance.layouts.launcher"),
      terminal: t("notifications:appearance.layouts.terminal"),
      reel: t("notifications:appearance.layouts.reel"),
      lights: t("notifications:appearance.layouts.lights"),
      vcr: t("notifications:appearance.layouts.vcr"),
      sheet: t("notifications:appearance.layouts.sheet"),
    } as Record<string, string>,
    footerHeader: t("notifications:appearance.footerHeader"),
    theme: t("notifications:appearance.theme"),
    themeDefault: t("notifications:appearance.themeDefault"),
    themeFallback: t("notifications:appearance.themeFallback"),
    density: t("notifications:appearance.density"),
    densities: {
      compact: t("notifications:appearance.densities.compact"),
      comfortable: t("notifications:appearance.densities.comfortable"),
      spacious: t("notifications:appearance.densities.spacious"),
    },
    textScale: t("notifications:appearance.textScale"),
    contrast: t("notifications:appearance.contrast"),
    reducedMotion: t("notifications:appearance.reducedMotion"),
    motions: {
      system: t("notifications:appearance.motions.system"),
      on: t("notifications:appearance.motions.on"),
      off: t("notifications:appearance.motions.off"),
    },
    sound: t("notifications:appearance.sound"),
    notificationPosition: t("notifications:appearance.notificationPosition"),
    positions: {
      "top-end": t("notifications:appearance.positions.top-end"),
      "top-start": t("notifications:appearance.positions.top-start"),
      "bottom-end": t("notifications:appearance.positions.bottom-end"),
      "bottom-start": t("notifications:appearance.positions.bottom-start"),
    },
    notificationStyle: t("notifications:appearance.notificationStyle"),
    styles: {
      toast: t("notifications:appearance.styles.toast"),
      banner: t("notifications:appearance.styles.banner"),
    },
    campaignThemes: t("notifications:appearance.campaignThemes"),
    forcedMotion: t("notifications:appearance.forcedMotion"),
    display: t("notifications:appearance.display"),
    displayHint: t("notifications:appearance.displayHint"),
    notifications: t("notifications:appearance.notifications"),
  };
}

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
  const strings = useAppearanceStrings();
  const rarities = useThemeRarities();
  return (
    <>
      <ul className="theme-gallery__list">
        {shown.map((theme) => {
          const p = presentationOf(theme);
          const active = theme.key === current || (theme.family && theme.family === currentTheme?.family);
          const name =
            theme.family === DEFAULT_FAMILY ? "Portalab" : theme.family ? theme.family : theme.name;
          const layout = `${strings.layouts[p.nav.desktop] ?? p.nav.desktop}${
            p.headerPosition === "bottom" ? ` · ${strings.footerHeader}` : ""
          }`;
          return (
            <li key={theme.key} className="theme-gallery__item">
              {/* #99: beside the card, which clips its children while off screen */}
              <RarityTag
                rarity={rarities.get(theme.key) ?? (theme.family ? rarities.get(theme.family) : undefined)}
              />
              <button
                type="button"
                className="theme-card"
                aria-pressed={Boolean(active)}
                data-rarity={
                  rarities.get(theme.key) ?? (theme.family ? rarities.get(theme.family) : undefined)
                }
                onClick={() => onChoose(theme)}
              >
                <ThemeMiniature theme={theme} />
                <span className="theme-card__name">
                  {name}
                  {active ? (
                    <span className="theme-card__current">
                      <Icon name="check" size={12} />
                      {strings.current}
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
  const t = useT();
  const strings = useAppearanceStrings();
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
      <PageHeader titleId={headingId} level={2} icon="palette" title={strings.title} />
      {effective.fallback ? <p role="status">{strings.themeFallback}</p> : null}
      <section className="appearance-card" aria-labelledby="theme-gallery">
        <h3 id="theme-gallery">{strings.gallery}</h3>
        <p className="ds-page-header__context">{strings.galleryHint}</p>
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
              label={strings.theme}
              value={preferences.theme ?? ""}
              disabled={disabled}
              aria-describedby={describedBy}
              onChange={(event) => set("theme")(event.target.value || null)}
            >
              <option value="">{strings.themeDefault}</option>
              {themes.map((theme) => (
                <option key={theme.key} value={theme.key}>
                  {theme.name}
                </option>
              ))}
            </SelectField>
          ))}
          {field("ui.colorMode", (disabled) => (
            <SelectField
              label={strings.colorMode}
              value={preferences.colorMode}
              disabled={disabled}
              onChange={(event) => set("colorMode")(event.target.value as UiPreferences["colorMode"])}
            >
              {Object.entries(strings.colorModes).map(([value, label]) => (
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
            label={strings.campaignThemes}
            checked={preferences.campaignThemes === "allow"}
            disabled={disabled}
            onChange={(event) => set("campaignThemes")(event.target.checked ? "allow" : "ignore")}
          />
        ))}
      </section>
      <PalettePicker />
      <LevelBadgePicker />
      <LevelUpPicker />
      <PluginLooks />
      <section className="appearance-card" aria-labelledby="appearance-display">
        <h3 id="appearance-display">{strings.display}</h3>
        <p className="ds-page-header__context">{strings.displayHint}</p>
        <div className="appearance-row">
          {field("ui.density", (disabled) => (
            <SelectField
              label={strings.density}
              value={preferences.density}
              disabled={disabled}
              onChange={(event) => set("density")(event.target.value as UiPreferences["density"])}
            >
              {Object.entries(strings.densities).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </SelectField>
          ))}
          {field("ui.reducedMotion", (disabled) => (
            <SelectField
              label={strings.reducedMotion}
              value={preferences.reducedMotion}
              disabled={disabled || policy.forceReducedMotion}
              hint={policy.forceReducedMotion ? strings.forcedMotion : undefined}
              onChange={(event) => set("reducedMotion")(event.target.value as UiPreferences["reducedMotion"])}
            >
              {Object.entries(strings.motions).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </SelectField>
          ))}
        </div>
        {field("ui.animations", (disabled) => (
          // #29: how much decorative motion — fewer looks at once and slower, or none
          <SelectField
            label={t("notifications:motionBudget.label")}
            value={preferences.animations}
            disabled={disabled}
            hint={t("notifications:motionBudget.hint")}
            onChange={(event) => set("animations")(event.target.value as UiPreferences["animations"])}
          >
            {(["all", "discreet", "none"] as const).map((value) => (
              <option key={value} value={value}>
                {t(`notifications:motionBudget.${value}`)}
              </option>
            ))}
          </SelectField>
        ))}
        {field("ui.cardActorBadge", (disabled) => (
          <CheckboxField
            label={t("gamification:cards.actorBadge")}
            checked={preferences.cardActorBadge}
            disabled={disabled}
            onChange={(event) => set("cardActorBadge")(event.target.checked)}
          />
        ))}
        {field("ui.textScale", (disabled) => (
          <div className="ds-field appearance-scale">
            <label htmlFor="ui-text-scale">{strings.textScale}</label>
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
              label={strings.contrast}
              checked={preferences.contrast === "high"}
              disabled={disabled}
              onChange={(event) => set("contrast")(event.target.checked ? "high" : "default")}
            />
          ))}
          {field("ui.soundEnabled", (disabled) => (
            <CheckboxField
              label={strings.sound}
              checked={preferences.soundEnabled}
              disabled={disabled}
              onChange={(event) => set("soundEnabled")(event.target.checked)}
            />
          ))}
        </div>
      </section>
      <UniverseLooks />
      <SafeModeSwitch />
      <NotificationLooks
        position={field("ui.notificationPosition", (disabled) => (
          <SelectField
            label={strings.notificationPosition}
            value={preferences.notificationPosition}
            disabled={disabled}
            onChange={(event) =>
              set("notificationPosition")(event.target.value as UiPreferences["notificationPosition"])
            }
          >
            {Object.entries(strings.positions).map(([value, label]) => (
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
