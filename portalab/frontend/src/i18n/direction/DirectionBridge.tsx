import type { ReactNode } from "react";
import { DirectionProvider } from "../../design-system/rtl/DirectionProvider";
import { useLocaleContext } from "../provider/I18nProvider";

/** Feeds the design system's direction provider (022) from the resolved locale (spec 026 T027). */
export function DirectionBridge({ children }: { children: ReactNode }) {
  const { language } = useLocaleContext();
  return <DirectionProvider language={language}>{children}</DirectionProvider>;
}
