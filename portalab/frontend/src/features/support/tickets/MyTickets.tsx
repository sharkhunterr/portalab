import { useId } from "react";
import "../support.css";
import { Link } from "react-router";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type TicketCard, useMyTickets } from "./api";

/** My tickets (spec 016 T025). */
export function TicketList({ items, label }: { items: TicketCard[]; label: string }) {
  const format = useFormat();
  return (
    <ul className="support-list" aria-label={label}>
      {items.map((ticket) => (
        <li key={ticket.id}>
          <Link to={`/support/tickets/${ticket.id}`}>
            {ticket.reference} · {ticket.title}
          </Link>{" "}
          <span className="support-meta">
            · {ticket.state} · {format.dateTime(ticket.updated_at)}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function MyTickets() {
  const t = useT();
  const headingId = useId();
  const tickets = useMyTickets();
  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId}>{t("support:mine.title")}</h2>
      <p>
        <Link to="/support/new">{t("support:mine.new")}</Link> ·{" "}
        <Link to="/feedback">{t("support:mine.feedback")}</Link>
      </p>
      {tickets.isPending ? <FunctionalState state="loading" /> : null}
      {tickets.data && tickets.data.length === 0 ? <p>{t("support:mine.empty")}</p> : null}
      {tickets.data ? <TicketList items={tickets.data} label={t("support:mine.title")} /> : null}
    </section>
  );
}

export default MyTickets;
