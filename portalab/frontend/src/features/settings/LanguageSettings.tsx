import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { api } from "../../api/client";
import { SelectField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { PolicyField, type PolicyState } from "../../design-system/components/PolicyField";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { SavedNote, SettingsCard, SettingsGrid, SettingsPage } from "../account/SettingsKit";

/**
 * Language & region (spec 026 T028; US1, US2, US3, US11): interface language, formats locale, time zone,
 * clock and first day of the week — independent choices. A setting locked by the administrator explains
 * why and keeps the user's own choice; a disabled language keeps the preference (``retained_language``).
 */
interface LanguageItem {
  code: string;
  name_native: string;
  name_en: string;
  direction: "ltr" | "rtl";
}

interface PreferenceView {
  key: string;
  value: unknown;
  locked: boolean;
  user_value: unknown;
  user_value_retained: boolean;
}

const LOCALES = ["en-US", "en-GB", "fr-FR", "fr-CA", "de-DE", "es-ES", "it-IT", "nl-NL", "pt-BR", "ja-JP"];
const DAYS = [0, 1, 2, 3, 4, 5, 6]; // i18n.firstDayOfWeek: 0 = Monday … 6 = Sunday

function zones(): string[] {
  const intl = Intl as unknown as { supportedValuesOf?: (key: string) => string[] };
  try {
    return intl.supportedValuesOf?.("timeZone") ?? ["UTC"];
  } catch {
    return ["UTC"];
  }
}

export function LanguageSettings() {
  const t = useT();
  const ctx = useLocaleContext();
  const format = useFormat();
  const client = useQueryClient();
  const languages = useQuery({
    queryKey: ["i18n", "languages"],
    queryFn: async () =>
      (await api.GET("/api/v1/i18n/languages")).data as unknown as { default: string; items: LanguageItem[] },
  });
  const views = useQuery({
    queryKey: ["me", "preferences", "views"],
    queryFn: async () =>
      ((await api.GET("/api/v1/me/preferences")).data as unknown as { preferences: PreferenceView[] })
        .preferences,
    retry: false,
  });
  const save = useMutation({
    mutationFn: async (values: Record<string, unknown>) => {
      await api.PUT("/api/v1/me/preferences", { body: values as never });
    },
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["me", "preferences"] });
      await client.invalidateQueries({ queryKey: ["i18n"] });
    },
  });
  const view = (key: string) => views.data?.find((v) => v.key === key);
  const value = (key: string) => {
    const v = view(key);
    return v?.user_value === null || v?.user_value === undefined ? "" : String(v.user_value);
  };
  const field = (key: string, render: (disabled: boolean, describedBy?: string) => ReactElement) => {
    const v = view(key);
    const state: PolicyState = v?.locked ? "locked" : "free";
    const retained = v?.locked && v.user_value_retained ? String(v.user_value) : null;
    return (
      <PolicyField id={key} state={state} retainedValue={retained}>
        {({ disabled, describedBy }) => render(disabled || save.isPending, describedBy)}
      </PolicyField>
    );
  };
  const set = (key: string) => (next: string) => save.mutate({ [key]: next === "" ? null : next });
  const dayName = (day: number) =>
    new Intl.DateTimeFormat(ctx.locale, { weekday: "long", timeZone: "UTC" }).format(
      new Date(Date.UTC(2024, 0, day + 1)), // 2024-01-01 is a Monday
    );
  return (
    <SettingsPage
      icon="globe"
      title={t("i18n:title")}
      lead={t("account:language.lead")}
      actions={<SavedNote shown={save.isSuccess} text={t("account:saved")} />}
    >
      {ctx.retained_language ? (
        <p role="status">{t("i18n:retained", { language: ctx.retained_language })}</p>
      ) : null}
      <SettingsGrid>
        <SettingsCard
          icon="globe"
          title={t("account:language.language")}
          hint={t("account:language.languageHint")}
        >
          {field("i18n.language", (disabled, describedBy) => (
            <SelectField
              label={t("i18n:language")}
              value={value("i18n.language")}
              disabled={disabled}
              aria-describedby={describedBy}
              onChange={(event) => set("i18n.language")(event.target.value)}
            >
              <option value="">{t("i18n:auto")}</option>
              {(languages.data?.items ?? []).map((language) => (
                <option
                  key={language.code}
                  value={language.code}
                  lang={language.code}
                  dir={language.direction}
                >
                  {language.name_native}
                </option>
              ))}
            </SelectField>
          ))}
        </SettingsCard>
        <SettingsCard
          icon="calendar"
          title={t("account:language.formats")}
          hint={t("account:language.formatsHint")}
        >
          <div className="settings-fields">
            {field("i18n.locale", (disabled, describedBy) => (
              <SelectField
                label={t("i18n:locale")}
                value={value("i18n.locale")}
                disabled={disabled}
                aria-describedby={describedBy}
                onChange={(event) => set("i18n.locale")(event.target.value)}
              >
                <option value="">{t("i18n:auto")}</option>
                {LOCALES.map((code) => (
                  <option key={code} value={code}>
                    {new Intl.DisplayNames([ctx.locale], { type: "language" }).of(code) ?? code}
                  </option>
                ))}
              </SelectField>
            ))}
            {field("i18n.timeZone", (disabled, describedBy) => (
              <SelectField
                label={t("i18n:timeZone")}
                value={value("i18n.timeZone")}
                disabled={disabled}
                aria-describedby={describedBy}
                onChange={(event) => set("i18n.timeZone")(event.target.value)}
              >
                <option value="">{t("i18n:auto")}</option>
                {zones().map((zone) => (
                  <option key={zone} value={zone}>
                    {zone}
                  </option>
                ))}
              </SelectField>
            ))}
            {field("i18n.hourCycle", (disabled, describedBy) => (
              <SelectField
                label={t("i18n:hourCycle")}
                value={value("i18n.hourCycle")}
                disabled={disabled}
                aria-describedby={describedBy}
                onChange={(event) => set("i18n.hourCycle")(event.target.value)}
              >
                <option value="">{t("i18n:auto")}</option>
                <option value="h12">{t("i18n:h12")}</option>
                <option value="h23">{t("i18n:h23")}</option>
              </SelectField>
            ))}
            {field("i18n.firstDayOfWeek", (disabled, describedBy) => (
              <SelectField
                label={t("i18n:firstDayOfWeek")}
                value={value("i18n.firstDayOfWeek")}
                disabled={disabled}
                aria-describedby={describedBy}
                onChange={(event) =>
                  save.mutate({
                    "i18n.firstDayOfWeek": event.target.value ? Number(event.target.value) : null,
                  })
                }
              >
                <option value="">{t("i18n:auto")}</option>
                {DAYS.map((day) => (
                  <option key={day} value={day}>
                    {dayName(day)}
                  </option>
                ))}
              </SelectField>
            ))}
          </div>
          <p className="settings-preview" aria-live="polite">
            <Icon name="clock" size={18} />
            {t("i18n:preview", { date: format.dateTime(new Date()) })}
          </p>
        </SettingsCard>
      </SettingsGrid>
    </SettingsPage>
  );
}

export default LanguageSettings;
