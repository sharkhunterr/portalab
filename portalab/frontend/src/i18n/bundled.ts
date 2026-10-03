import core from "../../../backend/locales/en/core.json";
import dashboard from "../../../backend/locales/en/dashboard.json";
import i18n from "../../../backend/locales/en/i18n.json";
import nav from "../../../backend/locales/en/nav.json";
import search from "../../../backend/locales/en/search.json";
import shell from "../../../backend/locales/en/shell.json";
import support from "../../../backend/locales/en/support.json";

/**
 * English base bundles shipped with the SPA (spec 026): the last-resort fallback when a catalog cannot be
 * loaded, and the strings used before the user's catalogs arrive. Same files as the backend's base bundles.
 */
export const BUNDLED: Record<string, Record<string, string>> = {
  core,
  dashboard,
  i18n,
  nav,
  search,
  shell,
  support,
};
export const DEFAULT_NAMESPACES = Object.keys(BUNDLED);

export function flatten(namespace: string, messages: Record<string, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(messages).map(([key, value]) => [`${namespace}:${key}`, value]));
}

export const BUNDLED_MESSAGES: Record<string, string> = Object.assign(
  {},
  ...Object.entries(BUNDLED).map(([namespace, messages]) => flatten(namespace, messages)),
);
