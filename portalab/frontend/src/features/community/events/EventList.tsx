import { useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Badge } from "../../../design-system/components/Content";
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
    <section aria-labelledby="community-events" className="ds-stack">
      <h2 id="community-events">{t("community:events.title")}</h2>
      {manager && editing === null ? (
        <Button onClick={() => setEditing("new")}>{t("community:events.create")}</Button>
      ) : null}
      {editing !== null ? (
        <EventEditor event={editing === "new" ? null : editing} onDone={() => setEditing(null)} />
      ) : null}
      {events.isError ? <FunctionalState state="unavailable" onRetry={() => events.refetch()} /> : null}
      {events.isSuccess && events.data.length === 0 ? (
        <p>
          {t("community:events.empty")} <Link to="/calendar">{t("community:events.emptyAction")}</Link>
        </p>
      ) : null}
      <ul className="ds-stack">
        {(events.data ?? []).map((event) => (
          <li key={event.id} id={`event-${event.id}`} className="ds-card ds-stack">
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
          </li>
        ))}
      </ul>
    </section>
  );
}
