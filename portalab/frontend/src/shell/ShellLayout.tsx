import { useMemo } from "react";
import { AiPanel } from "../features/ai/panel/AiPanel";
import { useAiAssistant } from "../features/ai/panel/useAiAssistant";
import { useLogout, useMe } from "../features/auth/useAuth";
import { useNotificationSummary } from "../features/notifications/bell/NotificationSlot";
import { ToastRegion } from "../features/notifications/toasts/ToastRegion";
import { useHelpSlot } from "../features/wiki/useHelpSlot";
import { AppShell } from "./AppShell";
import { ShellSlotsProvider } from "./slots/providers";

/** The shell as the router's root element, fed by the signed-in account and the slot providers. */
export function ShellLayout() {
  const me = useMe();
  const logout = useLogout();
  const notifications = useNotificationSummary(); // 010 bell
  const help = useHelpSlot(); // 011 contextual help
  const assistant = useAiAssistant(); // 018 assistant
  const slots = useMemo(
    () => ({ notifications, help, ai: assistant.slot }),
    [notifications, help, assistant.slot],
  );
  return (
    <ShellSlotsProvider value={slots}>
      <AppShell userName={me.data?.display_name ?? me.data?.login ?? ""} onSignOut={() => logout.mutate()} />
      <ToastRegion />
      <AiPanel {...assistant.panel} />
    </ShellSlotsProvider>
  );
}
