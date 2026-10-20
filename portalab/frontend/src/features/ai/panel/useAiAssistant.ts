import { useMemo, useState } from "react";
import type { AiProvider } from "../../../shell/slots/providers";
import { useAiStatus } from "../api";
import type { AiPanelProps } from "./AiPanel";

/** Feeds the shell's ``AiEntry`` slot (004) and drives the panel: opened with the current page context. */
export function useAiAssistant(): { slot: AiProvider; panel: AiPanelProps } {
  const status = useAiStatus();
  const [open, setOpen] = useState(false);
  const [context, setContext] = useState<{ route?: string; question?: string; asked?: number } | undefined>(
    undefined,
  );
  const available = Boolean(status.data?.available);
  const autoNavigate = Boolean(status.data?.auto_navigate);
  const slot = useMemo<AiProvider>(
    () => ({
      available,
      open: (ctx) => {
        setContext(
          ctx
            ? { route: ctx.route, ...(ctx.question ? { question: ctx.question, asked: Date.now() } : {}) }
            : undefined,
        );
        setOpen(true);
      },
    }),
    [available],
  );
  const name = status.data?.name || undefined; // issue 171: the name the administrators gave it
  // issue 171: what is left of today's allowance
  const quota = status.data?.daily_budget
    ? { budget: status.data.daily_budget, used: status.data.used_today ?? 0 }
    : undefined;
  return { slot, panel: { open, onOpenChange: setOpen, available, autoNavigate, context, name, quota } };
}
