import { useId, useState } from "react";
import "../support.css";
import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { EmptyState } from "../../../design-system/components/Placeholders";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type TicketCard, useMyTickets } from "./api";
import { isActive, PriorityBadge, StateBadge } from "./TicketBadges";

/**
 * My tickets (spec 016 T025, 027 T095): one card per ticket — reference, title, state and priority badges,
 * last update — filtered between the ones still in progress and the finished ones.
 */
export function TicketList({
  items,
  label,
  base = "/support/tickets",
}: {
  items: TicketCard[];
  label: string;
  /** Where a ticket opens: the member's page, or the team's (``/support/queue``). */
  base?: string;
}) {
  const t = useT();
  const format = useFormat();
  return (
    <ul className="support-list" aria-label={label}>
      {items.map((ticket) => (
        <li key={ticket.id} className="support-card" data-active={isActive(ticket.state)}>
          <span className="support-card__icon" aria-hidden="true">
            <Icon name="ticket" size={20} />
          </span>
          <span className="support-card__main">
            <span className="support-card__ref">{ticket.reference}</span>
            <Link to={`${base}/${ticket.id}`} className="support-card__title">
              {ticket.title}
            </Link>
            <span className="support-meta">
              {t("support:ticket.updated", {
                when: format.relative((Date.parse(ticket.updated_at) - Date.now()) / 1000),
              })}
            </span>
          </span>
          <span className="support-card__badges">
            <StateBadge state={ticket.state} />
            {ticket.priority !== "normal" ? <PriorityBadge priority={ticket.priority} /> : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

type Filter = "active" | "done" | "all";

export function MyTickets() {
  const t = useT();
  const headingId = useId();
  const tickets = useMyTickets();
  const [filter, setFilter] = useState<Filter>("active");
  const all = tickets.data ?? [];
  const pick = (f: Filter) =>
    all.filter((ticket) => f === "all" || (f === "active") === isActive(ticket.state));
  const shown = pick(filter);
  return (
    <section aria-labelledby={headingId} className="support-page">
      <PageHeader
        titleId={headingId}
        level={2}
        icon="ticket"
        title={t("support:mine.title")}
        context={t("support:mine.subtitle")}
        secondary={
          <Link className="ds-button ds-button--secondary" to="/feedback">
            {t("support:mine.feedback")}
          </Link>
        }
        primary={
          <Link className="ds-button ds-button--primary" to="/support/new" data-tour="new-ticket">
            <Icon name="plus" size={18} />
            {t("support:mine.new")}
          </Link>
        }
      />
      {tickets.isPending ? <FunctionalState state="loading" /> : null}
      {tickets.data && all.length === 0 ? (
        <EmptyState
          icon="lifebuoy"
          title={t("support:mine.empty")}
          action={
            <Link className="ds-button ds-button--primary" to="/support/new" data-tour="new-ticket">
              {t("support:mine.new")}
            </Link>
          }
        />
      ) : null}
      {all.length ? (
        <>
          <fieldset className="ds-subnav" aria-label={t("support:mine.title")}>
            {(["active", "done", "all"] as const).map((f) => (
              <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}>
                {t(`support:mine.${f}`)} · {pick(f).length}
              </button>
            ))}
          </fieldset>
          <TicketList items={shown} label={t("support:mine.title")} />
        </>
      ) : null}
    </section>
  );
}

export default MyTickets;
