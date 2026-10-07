import { useMemo, useState } from "react";
import type { NotificationSummary } from "../../../shell/slots/providers";
import { useUnreadCount } from "../api";

/**
 * Bell (spec 010 T013): feeds the shell's notification entry (004 slot) with the live unread count — the
 * count refreshes on each ``notification.created`` ping — and opens the notification panel (027) over the
 * page; the full center stays at ``/notifications``.
 */
export function useNotificationSummary(): {
  summary: NotificationSummary;
  open: boolean;
  setOpen: (open: boolean) => void;
} {
  const unread = useUnreadCount();
  const [open, setOpen] = useState(false);
  const count = unread.data ?? 0;
  const summary = useMemo(() => ({ unread: count, open: () => setOpen(true) }), [count]);
  return { summary, open, setOpen };
}
