import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api } from "../../../api/client";
import { AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { SelectField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useNotify } from "../../../design-system/components/Notification";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";

/**
 * Issue 451: the portal's system language and country (« fr-FR ») — the metadata's language, the country
 * whose age ratings count, the portal's default dates and numbers — set in one place by its administrator
 * (the arrival wizard set it once; nothing showed it since).
 */
const COUNTRIES = [
  "FR",
  "BE",
  "CH",
  "LU",
  "MC",
  "CA",
  "GB",
  "IE",
  "US",
  "AU",
  "NZ",
  "DE",
  "AT",
  "ES",
  "MX",
  "AR",
  "IT",
  "PT",
  "BR",
  "NL",
  "PL",
  "SE",
  "NO",
  "DK",
  "FI",
  "CZ",
  "GR",
  "TR",
  "RU",
  "UA",
  "JP",
  "KR",
  "CN",
  "IN",
  "MA",
  "DZ",
  "TN",
  "SN",
  "CI",
];
// a language's likeliest country, proposed when it is chosen
const LIKELY: Record<string, string> = {
  fr: "FR",
  en: "GB",
  de: "DE",
  es: "ES",
  it: "IT",
  pt: "PT",
  nl: "NL",
  pl: "PL",
  sv: "SE",
  nb: "NO",
  da: "DK",
  fi: "FI",
  cs: "CZ",
  el: "GR",
  tr: "TR",
  ru: "RU",
  uk: "UA",
  ja: "JP",
  ko: "KR",
  zh: "CN",
};
const KEYS = ["i18n.systemLanguage", "i18n.defaultLocale", "i18n.defaultLanguage"] as const;

interface Setting {
  key: string;
  value: unknown;
  source: string;
}

export function SystemLanguage() {
  const t = useT();
  const notify = useNotify();
  const client = useQueryClient();
  const ui = useLocaleContext();
  const settings = useQuery({
    queryKey: ["admin", "config", "system-language"],
    queryFn: async () => {
      const data = (await api.GET("/api/v1/admin/config")).data as unknown as { settings: Setting[] };
      return Object.fromEntries(
        (data?.settings ?? [])
          .filter((s) => (KEYS as readonly string[]).includes(s.key))
          .map((s) => [s.key, s]),
      ) as Partial<Record<(typeof KEYS)[number], Setting>>;
    },
  });
  const languages = useQuery({
    queryKey: ["i18n", "languages"],
    staleTime: 5 * 60_000,
    queryFn: async () =>
      (await api.GET("/api/v1/i18n/languages")).data as unknown as {
        default: string;
        items: Array<{ code: string; name_native: string }>;
      },
  });
  // what the portal follows now: the system language its administrator set, else the formatting locale, else
  // the interface's language (as the server reads it)
  const effective = useMemo(() => {
    const data = settings.data;
    const set = data?.["i18n.systemLanguage"];
    if (set?.value && set.source !== "default") return { tag: String(set.value), chosen: true };
    const chosen = (s: Setting | undefined): string | null =>
      s?.value && s.source !== "default" ? String(s.value) : null;
    const locale = data?.["i18n.defaultLocale"];
    const language = data?.["i18n.defaultLanguage"];
    const fallback: string =
      chosen(locale) ?? chosen(language) ?? String(locale?.value ?? language?.value ?? "en");
    return { tag: fallback, chosen: false };
  }, [settings.data]);
  // the current value until the administrator changes it
  const [draft, setDraft] = useState<{ language: string; country: string } | null>(null);
  const [currentLanguage = "en", currentRegion] = effective.tag.replace("_", "-").split("-");
  const current = {
    language: currentLanguage.toLowerCase(),
    country: (currentRegion?.toUpperCase() ?? LIKELY[currentLanguage.toLowerCase()] ?? "US").slice(0, 2),
  };
  const { language, country } = draft ?? current;
  const setLanguage = (next: string) =>
    setDraft({ language: next, country: LIKELY[next] ?? (draft ?? current).country });
  const setCountry = (next: string) => setDraft({ language, country: next });
  const names = useMemo(() => {
    try {
      return new Intl.DisplayNames([ui.language], { type: "region" });
    } catch {
      return null;
    }
  }, [ui.language]);
  const countries = [...COUNTRIES].sort((a, b) => (names?.of(a) ?? a).localeCompare(names?.of(b) ?? b));
  const enabled = new Set((languages.data?.items ?? []).map((item) => item.code));
  const save = useMutation({
    mutationFn: async () => {
      const tag = `${language}-${country}`;
      const changes = [
        { key: "i18n.systemLanguage", value: tag },
        { key: "i18n.defaultLocale", value: tag },
        ...(enabled.has(language) ? [{ key: "i18n.defaultLanguage", value: language }] : []),
      ].map((change) => ({ ...change, scope: "global", scope_ref: "", unset: false }));
      const body = { changes, reason: "system language" } as never;
      const preview = (await api.POST("/api/v1/admin/config/validate", { body })).data as unknown as
        | { ok: boolean; errors: Array<{ detail?: string }> }
        | undefined;
      if (preview && !preview.ok) throw new Error(preview.errors[0]?.detail ?? "invalid");
      const { error } = await api.PUT("/api/v1/admin/config", { body });
      if (error) throw new Error("not saved");
    },
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["admin", "config"] });
      await client.invalidateQueries({ queryKey: ["i18n"] });
      notify({
        severity: "success",
        title: t("admin:systemLanguage.saved", { tag: `${language}-${country}` }),
      });
    },
    onError: () => notify({ severity: "critical", title: t("admin:systemLanguage.error") }),
  });
  const languageName = (code: string) =>
    languages.data?.items.find((item) => item.code === code)?.name_native ?? code;
  const options = [
    ...new Set([...(languages.data?.items ?? []).map((i) => i.code), "fr", "en", language]),
  ].filter(Boolean);
  return (
    <AdminSection
      icon="globe"
      title={t("admin:systemLanguage.title")}
      description={t("admin:systemLanguage.description")}
    >
      <p className="admin-muted">
        {effective.chosen
          ? t("admin:systemLanguage.current", { tag: effective.tag })
          : t("admin:systemLanguage.unset", { tag: effective.tag })}
      </p>
      <div className="system-language">
        <SelectField
          label={t("admin:systemLanguage.language")}
          value={language}
          onChange={(event) => setLanguage(event.target.value)}
        >
          {options.map((code) => (
            <option key={code} value={code} lang={code}>
              {languageName(code)}
            </option>
          ))}
        </SelectField>
        <SelectField
          label={t("admin:systemLanguage.country")}
          hint={t("admin:systemLanguage.countryHint")}
          value={country}
          onChange={(event) => setCountry(event.target.value)}
        >
          {countries.map((code) => (
            <option key={code} value={code}>
              {names?.of(code) ?? code}
            </option>
          ))}
        </SelectField>
      </div>
      <Button type="button" disabled={!language || !country || save.isPending} onClick={() => save.mutate()}>
        <Icon name="check" size={16} />
        {t("admin:systemLanguage.save")}
      </Button>
    </AdminSection>
  );
}
