import { useEffect, useMemo, useState } from "react";
import type { NotificationSummary } from "../../../shell/slots/providers";
import { useUnreadCount } from "../api";

/**
 * Bell (spec 010 T013): feeds the shell's notification entry (004 slot) with the live unread count — the
 * count refreshes on each ``notification.created`` ping — and opens the notification panel (027) over the
 * page. Issue 112: the panel is the only place notifications are managed; ``/notifications`` (the palette, a
 * dashboard tile, an older link) opens it over the page one came from.
 */
export const OPEN_EVENT = "portalab:notifications-open";
export function useNotificationSummary(): {
  summary: NotificationSummary;
  open: boolean;
  setOpen: (open: boolean) => void;
} {
  const unread = useUnreadCount();
  const [open, setOpen] = useState(false);
  const count = unread.data ?? 0;
  const summary = useMemo(() => ({ unread: count, open: () => setOpen(true) }), [count]);
  useEffect(() => {
    const show = () => setOpen(true);
    window.addEventListener(OPEN_EVENT, show);
    return () => window.removeEventListener(OPEN_EVENT, show);
  }, []);
  return { summary, open, setOpen };
}
