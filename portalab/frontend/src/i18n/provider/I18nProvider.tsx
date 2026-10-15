import { useQueries, useQuery } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext, useEffect, useMemo } from "react";
import { IntlProvider } from "react-intl";
import { api } from "../../api/client";
import { externalMessages, useExternalRevision } from "../../design-system/themes/external/external";
import { BUNDLED_MESSAGES, DEFAULT_NAMESPACES, flatten } from "../bundled";
import { type PseudoLocale, pseudoCatalog } from "../pseudo/pseudo";

/**
 * ``<I18nProvider>`` (spec 026 T018; R2, R8): fetches the server-resolved ``LocaleContext`` and the
 * catalogs of the requested namespaces (effective base ⊕ overrides, fallback chain applied server side),
 * sets ``<html lang dir>`` and renders through react-intl. A catalog that fails to load falls back to the
 * last good copy (localStorage), then to the bundled English text — the UI never breaks.
 */
export interface LocaleContextValue {
  language: string;
  locale: string;
  time_zone: string;
  direction: "ltr" | "rtl";
  fallback_chain: string[];
  hour_cycle: "h12" | "h23" | null;
  first_day_of_week: number | null;
  retained_language: string | null;
}

export const DEFAULT_LOCALE: LocaleContextValue = {
  language: "en",
  locale: "en",
  time_zone: "UTC",
  direction: "ltr",
  fallback_chain: ["en"],
  hour_cycle: null,
  first_day_of_week: null,
  retained_language: null,
};

const LocaleCtx = createContext<LocaleContextValue>(DEFAULT_LOCALE);

const CACHE_KEY = "portalab.i18n";

/** Development only: ``?pseudo=en-XA|ar-XB`` renders every message through a pseudo-locale (R7). */
function pseudoLocale(): PseudoLocale | null {
  if (!import.meta.env.DEV) return null;
  const value = new URLSearchParams(window.location.search).get("pseudo");
  return value === "en-XA" || value === "ar-XB" ? value : null;
}

function readCache(language: string, namespace: string): Record<string, string> | null {
  try {
    const raw = window.localStorage.getItem(`${CACHE_KEY}.${language}.${namespace}`);
    return raw ? (JSON.parse(raw) as Record<string, string>) : null;
  } catch {
    return null;
  }
}

function writeCache(language: string, namespace: string, messages: Record<string, string>): void {
  try {
    window.localStorage.setItem(`${CACHE_KEY}.${language}.${namespace}`, JSON.stringify(messages));
  } catch {
    // private mode: no cache
  }
}

export function I18nProvider({
  children,
  namespaces = DEFAULT_NAMESPACES,
  override,
}: {
  children: ReactNode;
  namespaces?: string[];
  override?: Partial<LocaleContextValue>;
}) {
  const context = useQuery({
    queryKey: ["i18n", "context"],
    queryFn: async () => (await api.GET("/api/v1/i18n/context")).data as unknown as LocaleContextValue,
    staleTime: 5 * 60_000,
  });
  const pseudo = pseudoLocale();
  const locale: LocaleContextValue = {
    ...DEFAULT_LOCALE,
    ...(context.data ?? {}),
    ...(override ?? {}),
    ...(pseudo ? { language: pseudo, direction: pseudo === "ar-XB" ? "rtl" : "ltr" } : {}),
  };
  const catalogs = useQueries({
    queries: namespaces.map((namespace) => ({
      queryKey: ["i18n", "catalog", locale.language, namespace],
      enabled: context.isSuccess || override !== undefined,
      staleTime: 5 * 60_000,
      queryFn: async () => {
        try {
          const response = await api.GET("/api/v1/i18n/catalogs/{namespace}", {
            params: { path: { namespace }, query: { lang: locale.language } },
          });
          const messages = (response.data as unknown as { messages?: Record<string, string> } | undefined)
            ?.messages;
          if (!messages) throw new Error("catalog unavailable");
          writeCache(locale.language, namespace, messages);
          return messages;
        } catch {
          return readCache(locale.language, namespace) ?? {};
        }
      },
    })),
  });
  // issue 1: the names imported visual packs give their looks, over the catalogs
  const externalRevision = useExternalRevision();
  // biome-ignore lint/correctness/useExhaustiveDependencies: the packs' names follow their installation
  const messages = useMemo(() => {
    const merged: Record<string, string> = { ...BUNDLED_MESSAGES };
    catalogs.forEach((query, index) => {
      if (query.data) Object.assign(merged, flatten(namespaces[index] as string, query.data));
    });
    Object.assign(merged, externalMessages(locale.language));
    return pseudo ? pseudoCatalog(merged, pseudo) : merged;
  }, [catalogs, namespaces, pseudo, externalRevision, locale.language]);
  useEffect(() => {
    document.documentElement.lang = locale.language;
    document.documentElement.dir = locale.direction;
  }, [locale.language, locale.direction]);
  return (
    <LocaleCtx.Provider value={locale}>
      <IntlProvider
        locale={locale.locale}
        messages={messages}
        defaultLocale="en"
        timeZone={locale.time_zone}
        onError={() => undefined}
      >
        {children}
      </IntlProvider>
    </LocaleCtx.Provider>
  );
}

export function useLocaleContext(): LocaleContextValue {
  return useContext(LocaleCtx);
}
