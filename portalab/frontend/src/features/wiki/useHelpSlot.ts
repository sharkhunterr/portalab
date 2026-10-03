import { useMemo } from "react";
import { useLocation } from "react-router";
import { useT } from "../../i18n/hooks/useT";
import type { HelpResolver } from "../../shell/slots/providers";
import { useHelp } from "./api";

/**
 * Contextual help (spec 011 T016, 004 help slot): the current route becomes a help key (ids → ``detail``,
 * e.g. ``/services/<id>`` → ``services.detail``); the first wiki page the user may read for that key is
 * offered in the header. Nothing is shown when no permitted page exists.
 */
const ID = /^[0-9a-f-]{8,}$|^\d+$/i;

export function helpKey(pathname: string): string | null {
  const parts = pathname
    .split("/")
    .filter(Boolean)
    .map((part) => (ID.test(part) ? "detail" : part));
  return parts.length ? parts.join(".") : "home";
}

export function useHelpSlot(): HelpResolver {
  const t = useT();
  const location = useLocation();
  const key = helpKey(location.pathname);
  const help = useHelp(key);
  const first = help.data?.[0];
  return useMemo(
    () => ({
      resolve: () => (first ? { label: t("wiki:help", { title: first.title }), href: first.url } : null),
    }),
    [first, t],
  );
}
