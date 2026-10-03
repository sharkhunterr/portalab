import { useMemo } from "react";
import { type Translate, useT } from "../i18n/hooks/useT";

/** Shell strings (spec 004) — the English defaults; components read them through ``useShellStrings()``,
 * which resolves the ``shell`` and ``nav`` i18n catalogs (spec 026) and falls back to these values.
 * Navigation labels come as keys from the server (``label_key``). */
export const shellStrings = {
  brand: "Portalab",
  skip: "Skip to content",
  mainNav: "Main navigation",
  breadcrumb: "Breadcrumb",
  related: "Related",
  menu: "Menu",
  closeMenu: "Close menu",
  search: "Search",
  searchPlaceholder: "Search or jump to…",
  assistant: "Assistant",
  assistantUnavailable: "The assistant is not available right now.",
  notifications: "Notifications",
  account: "Account",
  signOut: "Sign out",
  palette: "Command palette",
  paletteInput: "Type a command or a destination",
  paletteEmpty: "No matching command.",
  paletteResults: (count: number) => `${count} result${count === 1 ? "" : "s"}`,
  shortcutsTitle: "Keyboard shortcuts",
  degraded: (count: number) =>
    `${count} services are degraded or unavailable. Navigation and search still work.`,
  notAvailable: "This page is not available.",
  notAvailableDetail: "It may not exist, or you may not have access to it.",
  unauthorized: "You do not have access to this page.",
  routeError: "This page could not be loaded.",
  retry: "Retry",
  goHome: "Go to the home page",
  homeTitle: "Welcome",
  homeEmpty: "Your dashboard arrives with the next release. Meanwhile:",
  navDegraded: "Navigation is limited right now.",
  labels: {
    "nav.home": "Home",
    "nav.account": "Account",
    "nav.appearance": "Appearance",
    "nav.language": "Language & region",
    "nav.search": "Search",
    "nav.incidents": "Incidents",
    "nav.statistics": "Statistics",
    "nav.admin.statistics": "Statistic definitions",
    "nav.admin.incidents": "Incident console",
    "nav.privacy": "Privacy",
    "nav.services": "Services",
    "nav.shortcuts": "Keyboard shortcuts",
    "nav.admin.control_center": "Control Center",
    "nav.admin.configuration": "Configuration",
    "nav.admin.services": "Manage services",
    "nav.admin.roles": "Roles & permissions",
    "nav.admin.privacy": "Privacy policies",
    "nav.admin.audit": "Audit",
    "nav.admin.events": "Events",
    "nav.admin.observability": "Observability",
    "nav.group.main": "Portal",
    "nav.group.me": "My account",
    "nav.group.admin": "Administration",
  } as Record<string, string>,
} as const;

export function label(key: string): string {
  return shellStrings.labels[key] ?? key;
}

type Strings = typeof shellStrings;
export type ShellStrings = {
  [K in Exclude<keyof Strings, "labels">]: Strings[K] extends (count: number) => string
    ? (count: number) => string
    : string;
} & { label: (key: string) => string };

const PLURALS = new Set(["degraded", "paletteResults"]);

/** Shell strings in the active language (catalog namespaces ``shell`` and ``nav``). */
export function useShellStrings(): ShellStrings {
  const t = useT();
  return useMemo(() => build(t), [t]);
}

function build(t: Translate): ShellStrings {
  const out: Record<string, unknown> = {};
  for (const key of Object.keys(shellStrings)) {
    if (key === "labels") continue;
    out[key] = PLURALS.has(key) ? (count: number) => t(`shell:${key}`, { count }) : t(`shell:${key}`);
  }
  out.label = (key: string) => {
    const text = t(`nav:${key}`);
    return text === key ? label(key) : text;
  };
  return out as ShellStrings;
}
