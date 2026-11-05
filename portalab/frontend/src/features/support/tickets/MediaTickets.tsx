import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { StateBadge } from "./TicketBadges";
import "../support.css";

/**
 * Issue 354: the tickets about a media, on its page — a warning badge that beats in its head while some are
 * open (how many), and their list at the bottom: mine, those of a public type (title and state only), all
 * of them for the team; the closed ones on demand.
 */
export const MEDIA_TICKETS_ID = "media-tickets";

export function useMediaTickets(mediaId: string, closed = false) {
  return useQuery({
    queryKey: ["support", "media", mediaId, closed],
    retry: false,
    queryFn: async () =>
      (
        await api.GET("/api/v1/tickets/media/{media_id}", {
          params: { path: { media_id: mediaId }, query: { closed } },
        })
      ).data ?? null,
  });
}

export function MediaTicketsBadge({ mediaId }: { mediaId: string }) {
  const t = useT();
  const open = useMediaTickets(mediaId).data?.open ?? 0;
  if (!open) return null;
  return (
    <a className="media-badge media-badge--tickets" href={`#${MEDIA_TICKETS_ID}`} data-tone="warn">
      <Icon name="flag" size={14} />
      {t("support:media.openBadge", { count: open })}
    </a>
  );
}

export function MediaTickets({ mediaId }: { mediaId: string }) {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const [closed, setClosed] = useState(false);
  const data = useMediaTickets(mediaId, closed).data;
  if (!data || (!data.open && !data.closed)) return null;
  return (
    <section id={MEDIA_TICKETS_ID} aria-labelledby={headingId} className="media-section media-tickets">
      <h3 id={headingId}>
        <Icon name="flag" size={18} />
        {t("support:media.listTitle")}
        <span className="media-tickets__count">{t("support:media.listCount", { count: data.open })}</span>
      </h3>
      {data.items.length ? (
        <ul className="media-tickets__list">
          {data.items.map((ticket) => {
            const to = data.staff
              ? `/support/queue/${ticket.id}`
              : ticket.mine
                ? `/support/tickets/${ticket.id}`
                : null;
            const body = (
              <>
                <span className="media-tickets__title">{ticket.title}</span>
                <span className="media-tickets__meta">
                  <StateBadge state={ticket.state} />
                  {ticket.mine ? <span className="ds-badge">{t("support:media.mine")}</span> : null}
                  <time dateTime={ticket.created_at}>{format.date(ticket.created_at)}</time>
                </span>
              </>
            );
            return (
              <li key={ticket.id} data-open={ticket.open || undefined}>
                {to ? (
                  <Link to={to} className="media-tickets__item">
                    {body}
                  </Link>
                ) : (
                  <div className="media-tickets__item">{body}</div>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="media-tickets__none">{t("support:media.noneOpen")}</p>
      )}
      {data.closed ? (
        <label className="media-tickets__filter">
          <input type="checkbox" checked={closed} onChange={(e) => setClosed(e.target.checked)} />
          {t("support:media.showClosed", { count: data.closed })}
        </label>
      ) : null}
    </section>
  );
}
