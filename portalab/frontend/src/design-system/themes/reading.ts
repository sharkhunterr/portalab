/**
 * #21: the reader's page colours — the book's pages are drawn in frames of their own, out of reach of the
 * portal's CSS variables, so the colours are given as values. « auto » follows the portal's theme.
 */
export type ReadingTheme = "auto" | "light" | "sepia" | "dark";

const PAGES = {
  light: { background: "#fdfdfb", color: "#1d1d1b", link: "#1f55c8" },
  sepia: { background: "#f4ecd8", color: "#3b2f1e", link: "#8a4b12" },
  dark: { background: "#17181c", color: "#d8d6d0", link: "#8ab4ff" },
} as const;

export function readingColors(theme: ReadingTheme): { background: string; color: string; link: string } {
  if (theme !== "auto") return PAGES[theme];
  return document.documentElement.dataset.colorScheme === "light" ? PAGES.light : PAGES.dark;
}
