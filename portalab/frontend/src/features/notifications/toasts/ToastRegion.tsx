import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { connectStream, type LiveEvent } from "../../../api/stream";
import { useNotify } from "../../../design-system/components/Notification";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import type { NotificationItem } from "../api";
import { fetchLatest } from "../api";
import { lookOf, severityOf } from "../presentation";

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
  const t = useT();
  const { language } = useLocaleContext();
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
        void fetchLatest(language).then((items) => {
          const item = items.find((candidate) => candidate.id === id);
          if (!item || shown.current.has(id)) return;
          shown.current.add(id);
          const look = lookOf(item);
          notify({
            severity: severityOf(item),
            tone: look.tone,
            icon: look.icon,
            title: item.title,
            // issue 186: what it is about and what it brought, under the title
            ...(toastBody(item, t) ? { body: toastBody(item, t) } : {}),
            ...(look.badge ? { badge: t(`notifications:badge.${look.badge}`) } : {}),
            ...(item.action_url ? { href: item.action_url, linkLabel: t("notifications:open") } : {}),
          });
        });
      },
    });
    return () => handle.close();
  }, [connect, client, notify, t, language]);
  return null;
}

function toastBody(item: NotificationItem, t: (key: string) => string): string {
  const rewards = (item.rewards ?? []).map(
    (reward) =>
      `+${reward.amount} ${reward.value === "coins" ? t("shell:coins") : t(`notifications:reward.${reward.value}`)}`,
  );
  if (item.boost) rewards.push(`×${item.boost}`);
  return [
    item.subtitle,
    item.body && item.body !== item.subtitle ? item.body : null,
    rewards.join(" · ") || null,
  ]
    .filter(Boolean)
    .join(" — ");
}
