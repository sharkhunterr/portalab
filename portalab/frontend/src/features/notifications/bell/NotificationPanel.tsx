import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type CenterFilter, type NotificationItem, useNotificationActions, useNotifications } from "../api";
import { lookOf, severityOf } from "../presentation";
import "../notifications.css";

/**
 * The bell's panel (027): the notification history opens over the page — a sheet from the side on large
 * screens, the whole screen on a phone — instead of leaving it. Newest first, grouped by day, unread ones
 * marked; a tap opens what the notification is about (and marks it read); all can be marked read at once;
 * the full center and the preferences are one link away.
 */
const TABS: Array<{ key: string; filter: CenterFilter }> = [
  { key: "all", filter: {} },
  { key: "unread", filter: { unread: true } },
  { key: "alerts", filter: { kind: "alert" } },
];

function dayOf(iso: string): "today" | "yesterday" | "week" | "earlier" {
  const at = new Date(iso);
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const time = at.getTime();
  if (time >= start) return "today";
  if (time >= start - 86_400_000) return "yesterday";
  if (time >= start - 6 * 86_400_000) return "week";
  return "earlier";
}

export function NotificationPanel({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useT();
  const [tab, setTab] = useState("all");
  const filter = TABS.find((x) => x.key === tab)?.filter ?? {};
  const query = useNotifications(filter, open); // read when the panel opens
  const actions = useNotificationActions();
  const pages = query.data?.pages ?? [];
  const items = pages.flatMap((page) => page.items);
  const unread = pages[0]?.unread ?? 0;
  const groups = (["today", "yesterday", "week", "earlier"] as const)
    .map((day) => [day, items.filter((item) => dayOf(item.updated_at) === day)] as const)
    .filter(([, list]) => list.length);
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="notif-panel__overlay" />
        <DialogPrimitive.Content className="notif-panel" aria-describedby={undefined}>
          <header className="notif-panel__head">
            <DialogPrimitive.Title className="notif-panel__title">
              <Icon name="bell" size={20} />
              {t("notifications:center.title")}
              {unread ? <span className="notif-panel__count">{unread > 99 ? "99+" : unread}</span> : null}
            </DialogPrimitive.Title>
            <div className="notif-panel__tools">
              <Button
                variant="ghost"
                size="icon"
                disabled={!unread || actions.readAll.isPending}
                onClick={() => actions.readAll.mutate()}
                title={t("notifications:center.markAll")}
                aria-label={t("notifications:center.markAll")}
              >
                <Icon name="check" size={18} />
              </Button>
              <Link
                to="/settings/notifications"
                className="ds-button ds-button--ghost ds-button--icon"
                title={t("notifications:panel.preferences")}
                aria-label={t("notifications:panel.preferences")}
                onClick={() => onOpenChange(false)}
              >
                <Icon name="settings" size={18} />
              </Link>
              <DialogPrimitive.Close asChild>
                <Button variant="ghost" size="icon" aria-label={t("notifications:panel.close")}>
                  <Icon name="close" size={18} />
                </Button>
              </DialogPrimitive.Close>
            </div>
          </header>
          <div className="notif-panel__tabs" role="tablist" aria-label={t("notifications:center.title")}>
            {TABS.map((x) => (
              <button
                key={x.key}
                type="button"
                role="tab"
                aria-selected={tab === x.key}
                className="notif-panel__tab"
                onClick={() => setTab(x.key)}
              >
                {t(`notifications:center.filter.${x.key}`)}
                {x.key === "unread" && unread ? <span>{unread}</span> : null}
              </button>
            ))}
          </div>
          <div className="notif-panel__body">
            {query.isPending ? <FunctionalState state="loading" /> : null}
            {query.isError ? <FunctionalState state="unavailable" onRetry={() => query.refetch()} /> : null}
            {query.isSuccess && items.length === 0 ? (
              <div className="notif-panel__empty">
                <Icon name="bell" size={36} />
                <p>{tab === "unread" ? t("notifications:panel.allRead") : t("notifications:center.empty")}</p>
              </div>
            ) : null}
            {groups.map(([day, list]) => (
              <section
                key={day}
                className="notif-panel__group"
                aria-label={t(`notifications:panel.day.${day}`)}
              >
                <h3>{t(`notifications:panel.day.${day}`)}</h3>
                <ol>
                  {list.map((item) => (
                    <PanelItem key={item.id} item={item} onDone={() => onOpenChange(false)} />
                  ))}
                </ol>
              </section>
            ))}
            {query.hasNextPage ? (
              <Button
                variant="ghost"
                onClick={() => query.fetchNextPage()}
                disabled={query.isFetchingNextPage}
              >
                {t("notifications:center.more")}
              </Button>
            ) : null}
          </div>
          <footer className="notif-panel__foot">
            <Link to="/notifications" onClick={() => onOpenChange(false)}>
              {t("notifications:panel.all")} <Icon name="chevron-right" size={14} />
            </Link>
          </footer>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function PanelItem({ item, onDone }: { item: NotificationItem; onDone: () => void }) {
  const t = useT();
  const format = useFormat();
  const navigate = useNavigate();
  const actions = useNotificationActions();
  const look = lookOf(item);
  const open = () => {
    if (!item.read) actions.read.mutate(item.id);
    if (item.action_url) {
      onDone();
      navigate(item.action_url);
    }
  };
  return (
    <li
      className="notif-row"
      data-read={item.read || undefined}
      data-tone={look.tone}
      data-severity={severityOf(item)}
    >
      <button type="button" className="notif-row__main" onClick={open}>
        <span className="notif-row__icon" aria-hidden="true">
          <Icon name={look.icon} size={18} />
        </span>
        <span className="notif-row__text">
          <span className="notif-row__title">
            {item.kind === "alert" ? (
              <span className="notif-row__badge">{t("notifications:kind.alert")}</span>
            ) : null}
            <strong>{item.title}</strong>
            {item.count > 1 ? <span className="notif-row__repeat">×{item.count}</span> : null}
          </span>
          {item.body ? <span className="notif-row__body">{item.body}</span> : null}
          <time dateTime={item.updated_at} title={format.dateTime(item.updated_at)}>
            {format.relative((Date.parse(item.updated_at) - Date.now()) / 1000)}
          </time>
        </span>
        {item.read ? null : (
          <span className="notif-row__dot">
            <span className="visually-hidden">{t("notifications:center.filter.unread")}</span>
          </span>
        )}
      </button>
      <div className="notif-row__actions">
        {item.read ? null : (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => actions.read.mutate(item.id)}
            aria-label={`${t("notifications:center.read")}: ${item.title}`}
            title={t("notifications:center.read")}
          >
            <Icon name="check" size={15} />
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => actions.archive.mutate(item.id)}
          aria-label={`${t("notifications:center.archive")}: ${item.title}`}
          title={t("notifications:center.archive")}
        >
          <Icon name="inbox" size={15} />
        </Button>
      </div>
    </li>
  );
}
