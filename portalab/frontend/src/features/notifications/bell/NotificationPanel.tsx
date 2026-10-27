import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { CurrencyShort } from "../../../design-system/site/SiteLook";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import {
  type BulkAction,
  type CenterFilter,
  type NotificationItem,
  useNotificationActions,
  useNotifications,
} from "../api";
import { lookOf, severityOf } from "../presentation";
import "../notifications.css";

/**
 * The bell's panel (027): the notification history opens over the page — a sheet from the side on large
 * screens, the whole screen on a phone — instead of leaving it. Newest first, grouped by day, unread ones
 * marked; a tap opens what the notification is about (and marks it read); all can be marked read at once;
 * the preferences are one link away. Issue 112: it is the only place notifications are managed — each one
 * read, archived (and brought back from the archive) or deleted, and several at once once « select » is on.
 */
const TABS: Array<{ key: string; filter: CenterFilter }> = [
  { key: "all", filter: {} },
  { key: "unread", filter: { unread: true } },
  { key: "alerts", filter: { kind: "alert" } },
  { key: "archived", filter: { archived: true } },
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
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirming, setConfirming] = useState(false);
  const filter = TABS.find((x) => x.key === tab)?.filter ?? {};
  const archivedTab = tab === "archived";
  const query = useNotifications(filter, open); // read when the panel opens
  const actions = useNotificationActions();
  const pages = query.data?.pages ?? [];
  const items = pages.flatMap((page) => page.items);
  const unread = pages[0]?.unread ?? 0;
  const shown = new Set(items.map((item) => item.id));
  const chosen = [...selected].filter((id) => shown.has(id));
  const stopSelecting = () => {
    setSelecting(false);
    setSelected(new Set());
    setConfirming(false);
  };
  const toggle = (id: string) => {
    setConfirming(false);
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const apply = (action: BulkAction) => {
    if (!chosen.length) return;
    actions.bulk.mutate({ ids: chosen, action }, { onSuccess: () => setSelected(new Set()) });
    setConfirming(false);
  };
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
                variant={selecting ? "secondary" : "ghost"}
                size="icon"
                aria-pressed={selecting}
                disabled={!items.length && !selecting}
                onClick={() => (selecting ? stopSelecting() : setSelecting(true))}
                title={t("notifications:panel.select")}
                aria-label={t("notifications:panel.select")}
              >
                <Icon name="list" size={18} />
              </Button>
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
                onClick={() => {
                  setTab(x.key);
                  setSelected(new Set());
                  setConfirming(false);
                }}
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
                <p>
                  {tab === "unread"
                    ? t("notifications:panel.allRead")
                    : archivedTab
                      ? t("notifications:panel.archivedEmpty")
                      : t("notifications:center.empty")}
                </p>
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
                    <PanelItem
                      key={item.id}
                      item={item}
                      onDone={() => onOpenChange(false)}
                      selecting={selecting}
                      checked={selected.has(item.id)}
                      onToggle={() => toggle(item.id)}
                    />
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
          {selecting ? (
            <section className="notif-panel__bulk" aria-label={t("notifications:panel.selection")}>
              <div className="notif-panel__bulk-head">
                <span aria-live="polite">{t("notifications:panel.selected", { count: chosen.length })}</span>
                <button
                  type="button"
                  className="ds-link"
                  onClick={() =>
                    setSelected(chosen.length === items.length ? new Set() : new Set(items.map((i) => i.id)))
                  }
                >
                  {chosen.length === items.length && items.length
                    ? t("notifications:panel.selectNone")
                    : t("notifications:panel.selectAll")}
                </button>
                <button type="button" className="ds-link" onClick={stopSelecting}>
                  {t("notifications:panel.done")}
                </button>
              </div>
              <div className="notif-panel__bulk-actions">
                {archivedTab ? (
                  <Button variant="secondary" disabled={!chosen.length} onClick={() => apply("unarchive")}>
                    <Icon name="undo" size={16} />
                    {t("notifications:panel.unarchive")}
                  </Button>
                ) : (
                  <>
                    <Button variant="secondary" disabled={!chosen.length} onClick={() => apply("read")}>
                      <Icon name="check" size={16} />
                      {t("notifications:panel.read")}
                    </Button>
                    <Button variant="secondary" disabled={!chosen.length} onClick={() => apply("archive")}>
                      <Icon name="inbox" size={16} />
                      {t("notifications:center.archive")}
                    </Button>
                  </>
                )}
                <Button
                  variant={confirming ? "danger" : "secondary"}
                  disabled={!chosen.length || actions.bulk.isPending}
                  onClick={() => (confirming ? apply("delete") : setConfirming(true))}
                >
                  <Icon name="trash" size={16} />
                  {confirming
                    ? t("notifications:panel.confirmDelete", { count: chosen.length })
                    : t("notifications:center.delete")}
                </Button>
              </div>
            </section>
          ) : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

const REWARD_ICONS: Record<string, string> = { xp: "sparkles", coins: "coins", contribution: "heart" };

/** Issue 186: what a notification brought — XP, the site's currency, contribution, a boost — as badges; issue 261:
 * a streak's multiplier too. */
export function Rewards({ item }: { item: NotificationItem }) {
  const t = useT();
  const format = useFormat();
  const rewards = item.rewards ?? [];
  if (!rewards.length && !item.boost && !item.streak) return null;
  return (
    <span className="notif-rewards">
      {rewards.map((reward) => (
        <span key={reward.value} className="notif-reward" data-value={reward.value}>
          <Icon name={REWARD_ICONS[reward.value] ?? "gift"} size={12} />+{format.number(reward.amount)}{" "}
          {reward.value === "coins" ? <CurrencyShort /> : t(`notifications:reward.${reward.value}`)}
        </span>
      ))}
      {item.streak ? (
        <span
          className="notif-reward"
          data-value="streak"
          title={t("notifications:reward.streak", { factor: format.number(item.streak) })}
        >
          <Icon name="flame" size={12} />×{format.number(item.streak)}
        </span>
      ) : null}
      {item.boost ? (
        <span className="notif-reward" data-value="boost">
          <Icon name="rocket" size={12} />×{item.boost}
        </span>
      ) : null}
    </span>
  );
}

function PanelItem({
  item,
  onDone,
  selecting,
  checked,
  onToggle,
}: {
  item: NotificationItem;
  onDone: () => void;
  selecting: boolean;
  checked: boolean;
  onToggle: () => void;
}) {
  const t = useT();
  const format = useFormat();
  const navigate = useNavigate();
  const actions = useNotificationActions();
  const look = lookOf(item);
  const open = () => {
    if (selecting) {
      onToggle();
      return;
    }
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
      data-selected={checked || undefined}
    >
      {selecting ? (
        <input
          type="checkbox"
          className="notif-row__check"
          checked={checked}
          onChange={onToggle}
          aria-label={`${t("notifications:panel.select")}: ${item.title}`}
        />
      ) : null}
      <span className="notif-row__icon" aria-hidden="true">
        <Icon name={look.icon} size={18} />
      </span>
      <div className="notif-row__content">
        <button
          type="button"
          className="notif-row__main"
          onClick={open}
          tabIndex={selecting ? -1 : undefined}
        >
          <span className="notif-row__title">
            {item.kind === "alert" ? (
              <span className="notif-row__badge">{t("notifications:kind.alert")}</span>
            ) : null}
            <strong>{item.title}</strong>
            {item.count > 1 ? <span className="notif-row__repeat">×{item.count}</span> : null}
            {item.read ? null : (
              <span className="notif-row__dot">
                <span className="visually-hidden">{t("notifications:center.filter.unread")}</span>
              </span>
            )}
          </span>
          {item.subtitle ? <span className="notif-row__subtitle">{item.subtitle}</span> : null}
          {item.body && item.body !== item.subtitle ? (
            <span className="notif-row__body">{item.body}</span>
          ) : null}
          <Rewards item={item} />
          <time dateTime={item.updated_at} title={format.dateTime(item.updated_at)}>
            {format.relative((Date.parse(item.updated_at) - Date.now()) / 1000)}
          </time>
        </button>
      </div>
      {selecting ? null : (
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
          {item.archived ? (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => actions.bulk.mutate({ ids: [item.id], action: "unarchive" })}
              aria-label={`${t("notifications:panel.unarchive")}: ${item.title}`}
              title={t("notifications:panel.unarchive")}
            >
              <Icon name="undo" size={15} />
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => actions.archive.mutate(item.id)}
              aria-label={`${t("notifications:center.archive")}: ${item.title}`}
              title={t("notifications:center.archive")}
            >
              <Icon name="inbox" size={15} />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => actions.remove.mutate(item.id)}
            aria-label={`${t("notifications:center.delete")}: ${item.title}`}
            title={t("notifications:center.delete")}
          >
            <Icon name="trash" size={15} />
          </Button>
        </div>
      )}
    </li>
  );
}
