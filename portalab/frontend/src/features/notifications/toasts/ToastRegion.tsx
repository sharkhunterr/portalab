import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { connectStream, type LiveEvent } from "../../../api/stream";
import { useNotify } from "../../../design-system/components/Notification";
import { fetchLatest } from "../api";
import { severityOf } from "../presentation";

/**
 * Live toasts (spec 010 T019): the content-free ``notification.created`` ping triggers a refetch; the new
 * item is shown through 022's ``NotificationArea`` (position, duration, style and sound from the user's
 * ``ui.*`` preferences; alerts are announced assertively, notifications politely; a critical alert stays
 * until acknowledged). Presentation never hides content: the item is always in the center.
 */
export interface ToastRegionProps {
  /** Injectable for tests. */
  connect?: typeof connectStream;
}

export function ToastRegion({ connect = connectStream }: ToastRegionProps) {
  const notify = useNotify();
  const client = useQueryClient();
  const shown = useRef(new Set<string>());
  useEffect(() => {
    if (connect === connectStream && typeof EventSource === "undefined") return;
    const handle = connect({
      topics: ["notification.created"],
      onEvent: (event: LiveEvent) => {
        void client.invalidateQueries({ queryKey: ["notifications"] });
        const id = (event.data as { id?: string } | null)?.id;
        if (!id || shown.current.has(id)) return;
        void fetchLatest().then((items) => {
          const item = items.find((candidate) => candidate.id === id);
          if (!item || shown.current.has(id)) return;
          shown.current.add(id);
          notify({
            severity: severityOf(item),
            title: item.title,
            ...(item.body ? { body: item.body } : {}),
          });
        });
      },
    });
    return () => handle.close();
  }, [connect, client, notify]);
  return null;
}
