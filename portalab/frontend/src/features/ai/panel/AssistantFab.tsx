import { type CSSProperties, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { useBottomOverlays } from "../../../shell/bottomOverlays";
import { useSlots } from "../../../shell/slots/providers";

/**
 * Issue 171 — the assistant from any page: a round button in the corner, drawn inside the shell so it sits
 * above the layout's own bars (a phone's bottom bar, a dock) — and above a player's bar when one is open (the
 * radio, an audiobook); only while an assistant answers, and not while its window is open.
 */
export function AssistantFab({ hidden }: { hidden: boolean }) {
  const t = useT();
  const { ai } = useSlots();
  const location = useLocation();
  const covered = useBottomOverlays();
  const [shell, setShell] = useState<HTMLElement | null>(null);
  useEffect(() => {
    setShell(document.querySelector<HTMLElement>(".shell"));
  }, []);
  if (!ai?.available || hidden) return null;
  const button = (
    <button
      type="button"
      className="ai-fab"
      style={{ "--overlay-bottom": `${covered}px` } as CSSProperties}
      aria-label={t("ai:panel.open")}
      title={t("ai:panel.open")}
      onClick={() => ai.open({ route: location.pathname })}
    >
      <Icon name="sparkles" size={24} />
    </button>
  );
  return shell ? createPortal(button, shell) : button;
}
