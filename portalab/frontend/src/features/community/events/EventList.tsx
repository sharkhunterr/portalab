import { useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Badge } from "../../../design-system/components/Content";
import { Icon } from "../../../design-system/components/Icon";
import { EmptyState } from "../../../design-system/components/Placeholders";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useHasPermission } from "../../authz/useMyPermissions";
import { SafeHtml } from "../../content/SafeHtml";
import { type CommunityEvent, useCommunityEvents, useEventAdmin } from "../api";
import { EventEditor } from "./EventEditor";

/** ``/community/events`` (spec 012 T014): upcoming events for this viewer's audience; managers edit them. */
export function EventList() {
  const t = useT();
  const format = useFormat();
  const events = useCommunityEvents();
  const { cancel } = useEventAdmin();
  const manager = useHasPermission("community.events.manage");
  const [editing, setEditing] = useState<CommunityEvent | "new" | null>(null);
  return (
    <section aria-label={t("community:events.title")} className="ds-stack">
      {manager && editing === null ? (
        <div className="community-actions">
          <Button onClick={() => setEditing("new")}>
            <Icon name="plus" size={16} />
            {t("community:events.create")}
          </Button>
        </div>
      ) : null}
      {editing !== null ? (
        <EventEditor event={editing === "new" ? null : editing} onDone={() => setEditing(null)} />
      ) : null}
      {events.isError ? <FunctionalState state="unavailable" onRetry={() => events.refetch()} /> : null}
      {events.isSuccess && events.data.length === 0 ? (
        <EmptyState
          icon="calendar"
          title={t("community:events.empty")}
          action={
            <Link className="ds-button ds-button--secondary" to="/calendar">
              {t("community:events.emptyAction")}
            </Link>
          }
        />
      ) : null}
      <ul className="community-events">
        {(events.data ?? []).map((event) => (
          <li
            key={event.id}
            id={`event-${event.id}`}
            className="community-event"
            data-cancelled={event.status === "cancelled" || undefined}
          >
            <span className="community-event__date" aria-hidden="true">
              <strong>{format.dayMonth(event.starts_at).day}</strong>
              <span>{format.dayMonth(event.starts_at).month}</span>
            </span>
            <div className="community-event__body ds-stack">
              <h3>
                {event.title}{" "}
                {event.status === "cancelled" ? <Badge>{t("community:events.cancelled")}</Badge> : null}
              </h3>
              <p className="community-meta">
                {event.all_day
                  ? `${format.date(event.starts_at)} · ${t("community:events.allDay")}`
                  : format.dateTime(event.starts_at)}
                {" · "}
                {t(`community:events.audience.${event.audience}`)}
              </p>
              <SafeHtml html={event.rendered_html} diagrams={false} />
              {manager && event.status !== "cancelled" ? (
                <div className="ds-stack--row">
                  <Button variant="secondary" onClick={() => setEditing(event)}>
                    {t("community:events.edit")}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      if (window.confirm(t("community:events.cancelConfirm"))) cancel.mutate(event.id);
                    }}
                  >
                    {t("community:events.cancel")}
                  </Button>
                </div>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
