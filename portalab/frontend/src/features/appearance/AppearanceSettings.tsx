import { useQuery } from "@tanstack/react-query";
import { type ReactElement, useId } from "react";
import { api } from "../../api/client";
import { usePreferences } from "../../design-system/a11y/PreferencesProvider";
import type { UiPreferences } from "../../design-system/a11y/preferences";
import { CheckboxField, SelectField } from "../../design-system/components/Field";
import { PageHeader } from "../../design-system/components/PageHeader";
import { PolicyField, type PolicyState } from "../../design-system/components/PolicyField";
import { useTheme } from "../../design-system/themes/ThemeProvider";

/**
 * Appearance & accessibility settings (spec 022): theme, density, text size, contrast, motion, sound and
 * notification appearance. Policy-locked settings explain why; the user's own choice is kept. Changing a
 * setting never changes data — only presentation. Strings externalized for i18n (026).
 */
export const appearanceStrings = {
  title: "Appearance & accessibility",
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

export function AppearanceSettings() {
  const headingId = useId();
  const { preferences, policy, setPreference } = usePreferences();
  const { themes, effective } = useTheme();
  const policyOf = usePolicyStates();
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
    <section aria-labelledby={headingId} className="account-page">
      <PageHeader titleId={headingId} level={2} icon="palette" title={appearanceStrings.title} />
      {effective.fallback ? <p role="status">{appearanceStrings.themeFallback}</p> : null}
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
      {field("ui.textScale", (disabled) => (
        <div className="ds-field">
          <label htmlFor="ui-text-scale">{appearanceStrings.textScale}</label>
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
          <output htmlFor="ui-text-scale">{Math.round(effective.textScale * 100)}%</output>
        </div>
      ))}
      {field("ui.contrast", (disabled) => (
        <CheckboxField
          label={appearanceStrings.contrast}
          checked={preferences.contrast === "high"}
          disabled={disabled}
          onChange={(event) => set("contrast")(event.target.checked ? "high" : "default")}
        />
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
      {field("ui.soundEnabled", (disabled) => (
        <CheckboxField
          label={appearanceStrings.sound}
          checked={preferences.soundEnabled}
          disabled={disabled}
          onChange={(event) => set("soundEnabled")(event.target.checked)}
        />
      ))}
      {field("ui.notificationPosition", (disabled) => (
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
      {field("ui.notificationStyle", (disabled) => (
        <SelectField
          label={appearanceStrings.notificationStyle}
          value={preferences.notificationStyle}
          disabled={disabled}
          onChange={(event) =>
            set("notificationStyle")(event.target.value as UiPreferences["notificationStyle"])
          }
        >
          {Object.entries(appearanceStrings.styles).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </SelectField>
      ))}
      {field("ui.campaignThemes", (disabled) => (
        <CheckboxField
          label={appearanceStrings.campaignThemes}
          checked={preferences.campaignThemes === "allow"}
          disabled={disabled}
          onChange={(event) => set("campaignThemes")(event.target.checked ? "allow" : "ignore")}
        />
      ))}
    </section>
  );
}
