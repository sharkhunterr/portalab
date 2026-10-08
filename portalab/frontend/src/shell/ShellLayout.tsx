import { useMemo } from "react";
import { AiPanel } from "../features/ai/panel/AiPanel";
import { useAiAssistant } from "../features/ai/panel/useAiAssistant";
import { useLogout, useMe } from "../features/auth/useAuth";
import { NotificationPanel } from "../features/notifications/bell/NotificationPanel";
import { useNotificationSummary } from "../features/notifications/bell/NotificationSlot";
import { ToastRegion } from "../features/notifications/toasts/ToastRegion";
import { TermsViewer } from "../features/terms/TermsViewer";
import { useHelpSlot } from "../features/wiki/useHelpSlot";
import { AppShell } from "./AppShell";
import { ShellSlotsProvider } from "./slots/providers";

/** The shell as the router's root element, fed by the signed-in account and the slot providers. */
export function ShellLayout() {
  const me = useMe();
  const logout = useLogout();
  const bell = useNotificationSummary(); // 010 bell — 027: opens the panel
  const notifications = bell.summary;
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
      <NotificationPanel open={bell.open} onOpenChange={bell.setOpen} />
      <AiPanel {...assistant.panel} />
      <TermsViewer />
    </ShellSlotsProvider>
  );
}
