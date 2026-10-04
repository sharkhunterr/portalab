import { useId } from "react";
import "../support.css";
import { Link } from "react-router";
import { ListItem } from "../../../design-system/components/Collections";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { EmptyState } from "../../../design-system/components/Placeholders";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type TicketCard, useMyTickets } from "./api";

/** My tickets (spec 016 T025). */
export function TicketList({ items, label }: { items: TicketCard[]; label: string }) {
  const format = useFormat();
  return (
    <ul className="support-list ds-card" aria-label={label}>
      {items.map((ticket) => (
        <ListItem
          key={ticket.id}
          leading={<Icon name="ticket" />}
          title={
            <Link to={`/support/tickets/${ticket.id}`}>
              {ticket.reference} · {ticket.title}
            </Link>
          }
          meta={format.dateTime(ticket.updated_at)}
          trailing={<span className="ds-badge">{ticket.state}</span>}
        />
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
      <PageHeader
        titleId={headingId}
        level={2}
        icon="ticket"
        title={t("support:mine.title")}
        secondary={
          <>
            <Link className="ds-button ds-button--secondary" to="/feedback">
              {t("support:mine.feedback")}
            </Link>
            <Link className="ds-button ds-button--primary" to="/support/new">
              {t("support:mine.new")}
            </Link>
          </>
        }
      />
      {tickets.isPending ? <FunctionalState state="loading" /> : null}
      {tickets.data && tickets.data.length === 0 ? (
        <EmptyState
          icon="lifebuoy"
          title={t("support:mine.empty")}
          action={
            <Link className="ds-button ds-button--primary" to="/support/new">
              {t("support:mine.new")}
            </Link>
          }
        />
      ) : null}
      {tickets.data ? <TicketList items={tickets.data} label={t("support:mine.title")} /> : null}
    </section>
  );
}

export default MyTickets;
