import type { ReactNode } from "react";
import { useMemo } from "react";
import { useNavigate } from "react-router";
import { ShellSlotsProvider } from "../../../shell/slots/providers";
import { useUnreadCount } from "../api";
import { ToastRegion } from "../toasts/ToastRegion";

/**
 * Bell (spec 010 T013): feeds the shell's notification entry (004 slot) with the live unread count — the
 * count refreshes on each ``notification.created`` ping — and opens the center. Mounts the live toasts.
 */
export function NotificationSlot({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const unread = useUnreadCount();
  const count = unread.data ?? 0;
  const value = useMemo(
    () => ({ notifications: { unread: count, open: () => navigate("/notifications") } }),
    [count, navigate],
  );
  return (
    <ShellSlotsProvider value={value}>
      {children}
      <ToastRegion />
    </ShellSlotsProvider>
  );
}
