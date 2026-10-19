import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useEffect, useMemo } from "react";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { SiteLookContext } from "../../design-system/site/SiteLook";

export type Site = components["schemas"]["SiteOut"];
export const SITE_KEY = ["site"] as const;

export const DEFAULT_SITE: Site = {
  name: "Portalab",
  short_name: "Portalab",
  custom: false,
  tagline: {},
  currency: {},
  currency_short: null,
  currency_icon: null,
  logo: null,
  icon: null,
  version: 0,
};

/**
 * Issue 159: the site's identity — its name, short name, slogan, logo, icon and currency. Public (the
 * sign-in page shows it); Portalab's own until the administrators set theirs, or while it cannot be read.
 */
export function useSite(): Site {
  const query = useQuery({
    queryKey: SITE_KEY,
    staleTime: 5 * 60_000,
    retry: false,
    queryFn: async () => siteOf((await api.GET("/api/v1/auth/site")).data),
  });
  return query.data ?? DEFAULT_SITE;
}

/** Whatever answered, a whole identity: Portalab's own for anything missing or of the wrong kind. */
function siteOf(data: unknown): Site {
  const raw = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
  const text = (value: unknown) => (typeof value === "string" && value ? value : null);
  const record = (value: unknown) =>
    value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, never>) : {};
  const name = text(raw.name) ?? DEFAULT_SITE.name;
  return {
    name,
    short_name: text(raw.short_name) ?? name,
    custom: raw.custom === true,
    tagline: record(raw.tagline),
    currency: record(raw.currency),
    currency_short: text(raw.currency_short),
    currency_icon: text(raw.currency_icon),
    logo: text(raw.logo),
    icon: text(raw.icon),
    version: typeof raw.version === "number" ? raw.version : 0,
  };
}

/** A text written per language: the language's own, its base language's, English's, then the first one. */
export function inLanguage(texts: Record<string, string>, language: string): string | undefined {
  const base = language.split("-")[0] ?? language;
  return texts[language] ?? texts[base] ?? texts.en ?? Object.values(texts)[0];
}

function headLink(rel: string, href: string | null) {
  let link = document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`);
  if (!href) {
    link?.remove();
    return;
  }
  if (!link) {
    link = document.createElement("link");
    link.rel = rel;
    document.head.appendChild(link);
  }
  link.href = href;
}

/**
 * The site's identity where the whole page shows it: the tab's title and icon, the home-screen manifest —
 * and, for the design system, the currency's icon and short name.
 */
export function SiteRoot({ children }: { children: ReactNode }) {
  const site = useSite();
  useEffect(() => {
    document.title = site.name;
    headLink("icon", site.icon);
    headLink("manifest", `/api/v1/auth/site/manifest?v=${site.version}`);
  }, [site.name, site.icon, site.version]);
  const look = useMemo(
    () => ({ currencyIcon: site.currency_icon, currencyShort: site.currency_short }),
    [site.currency_icon, site.currency_short],
  );
  return <SiteLookContext.Provider value={look}>{children}</SiteLookContext.Provider>;
}
