import { useId, useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type CenterFilter, type NotificationItem, useNotificationActions, useNotifications } from "../api";
import { severityOf } from "../presentation";
import "../notifications.css";

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
  return (
    <li className="notification-item" data-read={item.read} data-kind={item.kind} data-severity={severity}>
      <div className="notification-item__head">
        <FunctionalState
          state={severity === "critical" ? "error" : severity === "warning" ? "partial" : "available"}
          label={t(`notifications:kind.${item.kind}`)}
        />
        <span className="notification-item__priority">{t(`notifications:priority.${item.priority}`)}</span>
        {item.read ? null : <span className="ds-badge">{t("notifications:center.filter.unread")}</span>}
      </div>
      <h3 className="notification-item__title">
        {item.action_url ? <Link to={item.action_url}>{item.title}</Link> : item.title}
        {item.count > 1 ? (
          <span className="notification-item__count">
            {" "}
            {t("notifications:repeated", { count: item.count })}
          </span>
        ) : null}
      </h3>
      {item.body ? <p>{item.body}</p> : null}
      <p className="notification-item__meta">
        <time dateTime={item.updated_at}>{format.dateTime(item.updated_at)}</time>
      </p>
      <div className="ds-stack ds-stack--row">
        {item.read ? null : (
          <Button variant="secondary" onClick={() => actions.read.mutate(item.id)}>
            {t("notifications:center.read")}
            <span className="visually-hidden">: {item.title}</span>
          </Button>
        )}
        {item.archived ? null : (
          <Button variant="secondary" onClick={() => actions.archive.mutate(item.id)}>
            {t("notifications:center.archive")}
            <span className="visually-hidden">: {item.title}</span>
          </Button>
        )}
        <Button variant="danger" onClick={() => actions.remove.mutate(item.id)}>
          {t("notifications:center.delete")}
          <span className="visually-hidden">: {item.title}</span>
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
      <h2 id={headingId}>{t("notifications:center.title")}</h2>
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
