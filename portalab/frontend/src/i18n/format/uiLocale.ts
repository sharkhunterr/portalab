/**
 * Issue 457: the interface's language (« fr », « en »), as the i18n provider set it on ``<html lang>`` — for
 * a date or a time written outside ``useFormat()``. Never the browser's: a member who chose English reads
 * English months on a French browser.
 */
export function uiLocale(): string | undefined {
  return (typeof document !== "undefined" && document.documentElement.lang) || undefined;
}
