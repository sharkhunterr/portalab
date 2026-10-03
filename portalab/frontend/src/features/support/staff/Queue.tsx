import { useId, useState } from "react";
import "../support.css";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useQueue } from "../tickets/api";
import { TicketList } from "../tickets/MyTickets";

/** Support queue (spec 016 T025, staff): filter by state, unassigned, text. */
const STATES = ["open", "in_progress", "waiting_user", "resolved", "closed", "cancelled"];

export function Queue() {
  const t = useT();
  const headingId = useId();
  const [state, setState] = useState("open");
  const [unassigned, setUnassigned] = useState(false);
  const [q, setQ] = useState("");
  const queue = useQueue({ state, unassigned, q });
  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId}>{t("support:queue.title")}</h2>
      <search>
        <fieldset className="support-filters">
          <legend className="visually-hidden">{t("support:queue.filters")}</legend>
          <SelectField
            label={t("support:ticket.state")}
            value={state}
            onChange={(e) => setState(e.target.value)}
          >
            <option value="">{t("support:queue.all")}</option>
            {STATES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </SelectField>
          <CheckboxField
            label={t("support:queue.unassigned")}
            checked={unassigned}
            onChange={(e) => setUnassigned(e.target.checked)}
          />
          <TextField label={t("support:queue.search")} value={q} onChange={(e) => setQ(e.target.value)} />
        </fieldset>
      </search>
      {queue.isError ? <FunctionalState state="unauthorized" /> : null}
      {queue.data && queue.data.items.length === 0 ? <p>{t("support:queue.empty")}</p> : null}
      {queue.data ? <TicketList items={queue.data.items} label={t("support:queue.title")} /> : null}
    </section>
  );
}

export default Queue;
