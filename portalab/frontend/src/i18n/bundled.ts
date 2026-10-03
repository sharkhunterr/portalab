import ai from "../../../backend/locales/en/ai.json";
import automations from "../../../backend/locales/en/automations.json";
import calendar from "../../../backend/locales/en/calendar.json";
import campaigns from "../../../backend/locales/en/campaigns.json";
import community from "../../../backend/locales/en/community.json";
import content from "../../../backend/locales/en/content.json";
import core from "../../../backend/locales/en/core.json";
import dashboard from "../../../backend/locales/en/dashboard.json";
import gamification from "../../../backend/locales/en/gamification.json";
import i18n from "../../../backend/locales/en/i18n.json";
import marketplace from "../../../backend/locales/en/marketplace.json";
import media from "../../../backend/locales/en/media.json";
import nav from "../../../backend/locales/en/nav.json";
import news from "../../../backend/locales/en/news.json";
import notifications from "../../../backend/locales/en/notifications.json";
import search from "../../../backend/locales/en/search.json";
import shell from "../../../backend/locales/en/shell.json";
import statistics from "../../../backend/locales/en/statistics.json";
import support from "../../../backend/locales/en/support.json";
import wiki from "../../../backend/locales/en/wiki.json";

/**
 * English base bundles shipped with the SPA (spec 026): the last-resort fallback when a catalog cannot be
 * loaded, and the strings used before the user's catalogs arrive. Same files as the backend's base bundles.
 */
export const BUNDLED: Record<string, Record<string, string>> = {
  ai,
  automations,
  calendar,
  campaigns,
  community,
  content,
  core,
  dashboard,
  gamification,
  i18n,
  marketplace,
  media,
  nav,
  news,
  notifications,
  search,
  shell,
  statistics,
  support,
  wiki,
};
export const DEFAULT_NAMESPACES = Object.keys(BUNDLED);

export function flatten(namespace: string, messages: Record<string, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(messages).map(([key, value]) => [`${namespace}:${key}`, value]));
}

export const BUNDLED_MESSAGES: Record<string, string> = Object.assign(
  {},
  ...Object.entries(BUNDLED).map(([namespace, messages]) => flatten(namespace, messages)),
);
