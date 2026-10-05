import { useId, useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type CenterFilter, type NotificationItem, useNotificationActions, useNotifications } from "../api";
import { lookOf, severityOf } from "../presentation";
import "../notifications.css";
import { PageHeader } from "../../../design-system/components/PageHeader";

/**
 * Notification center (spec 010 T013): unread and important items first; alerts and notifications are
 * told apart by text badges (kind, priority) and the severity icon, not by color; read, archive, delete and
 * "mark all as read"; filters for unread items and alerts.
 */
const FILTERS: { key: string; label: string; filter: CenterFilter }[] = [
  { key: "all", label: "notifications:center.filter.all", filter: {} },
  { key: "unread", label: "notifications:center.filter.unread", filter: { unread: true } },
  { key: "alerts", label: "notifications:center.filter.alerts", filter: { kind: "alert" } },
];

function Item({ item }: { item: NotificationItem }) {
  const t = useT();
  const format = useFormat();
  const actions = useNotificationActions();
  const severity = severityOf(item);
  const look = lookOf(item);
  const ago = format.relative((Date.parse(item.updated_at) - Date.now()) / 1000);
  return (
    <li
      className="notification-item"
      data-read={item.read}
      data-kind={item.kind}
      data-severity={severity}
      data-tone={look.tone}
    >
      <span className="notification-item__icon" aria-hidden="true">
        <Icon name={look.icon} size={20} />
      </span>
      <div className="notification-item__main">
        <p className="notification-item__head">
          {item.read ? null : (
            <span className="notification-item__dot" title={t("notifications:center.filter.unread")} />
          )}
          {item.kind === "alert" ? (
            <span className="notification-item__badge" data-priority="critical">
              {t("notifications:kind.alert")}
            </span>
          ) : (
            <span className="visually-hidden">{t(`notifications:kind.${item.kind}`)}</span>
          )}
          <strong className="notification-item__title">
            {item.action_url ? <Link to={item.action_url}>{item.title}</Link> : item.title}
          </strong>
          {item.count > 1 ? (
            <span className="notification-item__count">
              {t("notifications:repeated", { count: item.count })}
            </span>
          ) : null}
        </p>
        {item.body ? <p className="notification-item__body">{item.body}</p> : null}
        <p className="notification-item__meta">
          <time dateTime={item.updated_at} title={format.dateTime(item.updated_at)}>
            {ago}
          </time>
          {look.badge ? (
            <span className="notification-item__badge">{t(`notifications:badge.${look.badge}`)}</span>
          ) : null}
          {item.priority === "high" || item.priority === "critical" ? (
            <span className="notification-item__badge" data-priority={item.priority}>
              {t(`notifications:priority.${item.priority}`)}
            </span>
          ) : null}
        </p>
      </div>
      <div className="notification-item__actions">
        {item.read ? null : (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => actions.read.mutate(item.id)}
            title={t("notifications:center.read")}
          >
            <Icon name="check" size={16} />
            <span className="visually-hidden">
              {t("notifications:center.read")}: {item.title}
            </span>
          </Button>
        )}
        {item.archived ? null : (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => actions.archive.mutate(item.id)}
            title={t("notifications:center.archive")}
          >
            <Icon name="inbox" size={16} />
            <span className="visually-hidden">
              {t("notifications:center.archive")}: {item.title}
            </span>
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => actions.remove.mutate(item.id)}
          title={t("notifications:center.delete")}
        >
          <Icon name="trash" size={16} />
          <span className="visually-hidden">
            {t("notifications:center.delete")}: {item.title}
          </span>
        </Button>
      </div>
    </li>
  );
}

export function NotificationCenter() {
  const t = useT();
  const headingId = useId();
  const [active, setActive] = useState("all");
  const filter = FILTERS.find((f) => f.key === active)?.filter ?? {};
  const query = useNotifications(filter);
  const actions = useNotificationActions();
  const pages = query.data?.pages ?? [];
  const items = pages.flatMap((page) => page.items);
  const unread = pages[0]?.unread ?? 0;
  return (
    <section aria-labelledby={headingId} className="notification-center">
      <PageHeader titleId={headingId} level={2} icon="bell" title={t("notifications:center.title")} />
      <p aria-live="polite">{t("notifications:center.unread", { count: unread })}</p>
      <div className="ds-stack ds-stack--row">
        <fieldset className="notification-center__filters">
          <legend className="visually-hidden">{t("notifications:center.title")}</legend>
          {FILTERS.map((f) => (
            <Button
              key={f.key}
              variant={f.key === active ? "primary" : "secondary"}
              aria-pressed={f.key === active}
              onClick={() => setActive(f.key)}
            >
              {t(f.label)}
            </Button>
          ))}
        </fieldset>
        <Button variant="secondary" disabled={!unread} onClick={() => actions.readAll.mutate()}>
          {t("notifications:center.markAll")}
        </Button>
      </div>
      {query.isPending ? <FunctionalState state="loading" /> : null}
      {query.isError ? <FunctionalState state="unavailable" onRetry={() => query.refetch()} /> : null}
      {query.isSuccess && items.length === 0 ? <p>{t("notifications:center.empty")}</p> : null}
      <ol className="notification-list">
        {items.map((item) => (
          <Item key={item.id} item={item} />
        ))}
      </ol>
      {query.hasNextPage ? (
        <Button variant="secondary" onClick={() => query.fetchNextPage()}>
          {t("notifications:center.more")}
        </Button>
      ) : null}
    </section>
  );
}

export default NotificationCenter;
