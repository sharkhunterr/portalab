import { useMemo } from "react";
import { useNavigate } from "react-router";
import type { NotificationSummary } from "../../../shell/slots/providers";
import { useUnreadCount } from "../api";

/**
 * Bell (spec 010 T013): feeds the shell's notification entry (004 slot) with the live unread count — the
 * count refreshes on each ``notification.created`` ping — and opens the center.
 */
export function useNotificationSummary(): NotificationSummary {
  const navigate = useNavigate();
  const unread = useUnreadCount();
  const count = unread.data ?? 0;
  return useMemo(() => ({ unread: count, open: () => navigate("/notifications") }), [count, navigate]);
}
