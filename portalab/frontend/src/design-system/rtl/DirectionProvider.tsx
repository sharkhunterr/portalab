import { createContext, type ReactNode, useContext, useEffect } from "react";

/**
 * Direction & language (spec 022 T024, R8): ``dir``/``lang`` come from i18n's ``LocaleContext`` (spec 026,
 * contract only for now). Layout uses CSS logical properties; directional icons listed here are mirrored
 * in RTL.
 */
export type Direction = "ltr" | "rtl";

export interface LocaleContextValue {
  language: string;
  direction: Direction;
}

const RTL_LANGUAGES = new Set(["ar", "he", "fa", "ur", "ps", "yi", "dv", "ku", "sd", "ug"]);
export const MIRRORED_ICONS: ReadonlySet<string> = new Set([
  "arrow-left",
  "arrow-right",
  "chevron-left",
  "chevron-right",
  "back",
  "forward",
  "reply",
  "undo",
  "redo",
  "list-indent",
]);

export function directionOf(language: string): Direction {
  return RTL_LANGUAGES.has((language.split("-")[0] ?? "").toLowerCase()) ? "rtl" : "ltr";
}

export const LocaleContext = createContext<LocaleContextValue>({ language: "en", direction: "ltr" });

export function DirectionProvider({ language, children }: { language: string; children: ReactNode }) {
  const direction = directionOf(language);
  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = direction;
  }, [language, direction]);
  return <LocaleContext.Provider value={{ language, direction }}>{children}</LocaleContext.Provider>;
}

export function useDirection(): LocaleContextValue {
  return useContext(LocaleContext);
}

/** Inline style flipping a directional icon in RTL (non-directional icons are never mirrored). */
export function mirrorStyle(icon: string, direction: Direction): { transform?: string } {
  return direction === "rtl" && MIRRORED_ICONS.has(icon) ? { transform: "scaleX(-1)" } : {};
}
