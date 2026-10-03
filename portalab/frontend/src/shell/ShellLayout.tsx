import { useMemo } from "react";
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
  const slots = useMemo(() => ({ notifications, help }), [notifications, help]);
  return (
    <ShellSlotsProvider value={slots}>
      <AppShell userName={me.data?.display_name ?? me.data?.login ?? ""} onSignOut={() => logout.mutate()} />
      <ToastRegion />
    </ShellSlotsProvider>
  );
}
