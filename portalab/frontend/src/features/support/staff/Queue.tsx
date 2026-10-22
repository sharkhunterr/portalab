import { useState } from "react";
import "../support.css";
import { AdminPage } from "../../../design-system/admin/AdminKit";
import { Icon } from "../../../design-system/components/Icon";
import { EmptyState } from "../../../design-system/components/Placeholders";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useQueue } from "../tickets/api";
import { TicketList } from "../tickets/MyTickets";
import { stateLabel } from "../tickets/TicketBadges";

/** Support queue (spec 016 T025, 027 T095, staff): state chips, "unassigned" toggle and a text search. */
const STATES = ["open", "in_progress", "waiting_user", "resolved", "closed", "cancelled"];

export function Queue() {
  const t = useT();
  const [state, setState] = useState("open");
  const [unassigned, setUnassigned] = useState(false);
  const [q, setQ] = useState("");
  const queue = useQueue({ state, unassigned, q });
  const items = queue.data?.items ?? [];
  return (
    <AdminPage icon="inbox" title={t("support:queue.title")} description={t("support:queue.subtitle")}>
      <search className="support-toolbar">
        <fieldset className="ds-subnav" aria-label={t("support:ticket.state")}>
          <button type="button" aria-pressed={!state} onClick={() => setState("")}>
            {t("support:queue.all")}
          </button>
          {STATES.map((s) => (
            <button key={s} type="button" aria-pressed={state === s} onClick={() => setState(s)}>
              {s === "waiting_user" ? t("support:queue.waitingMember") : stateLabel(t, s)}
            </button>
          ))}
        </fieldset>
        <button
          type="button"
          className="ds-button ds-button--ghost"
          aria-pressed={unassigned}
          onClick={() => setUnassigned(!unassigned)}
        >
          <Icon name={unassigned ? "check" : "user"} size={16} />
          {t("support:queue.unassigned")}
        </button>
        <label className="support-search">
          <Icon name="search" size={18} />
          <span className="visually-hidden">{t("support:queue.search")}</span>
          <input
            type="search"
            value={q}
            placeholder={t("support:queue.search")}
            onChange={(e) => setQ(e.target.value)}
          />
        </label>
      </search>
      {queue.isError ? <FunctionalState state="unauthorized" /> : null}
      {queue.data ? (
        <p className="support-meta">{t("support:queue.count", { count: items.length })}</p>
      ) : null}
      {queue.data && items.length === 0 ? (
        <EmptyState
          icon="inbox"
          title={t("support:queue.empty")}
          action={{ label: t("support:queue.all"), onSelect: () => setState("") }}
        />
      ) : null}
      {items.length ? (
        <TicketList items={items} label={t("support:queue.title")} base="/support/queue" />
      ) : null}
    </AdminPage>
  );
}

export default Queue;
