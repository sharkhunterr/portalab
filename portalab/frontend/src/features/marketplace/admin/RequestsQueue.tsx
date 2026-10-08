import { useState } from "react";
import { AdminSection, StatusBadge } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type MarketRequest, useDecideRequest, useRequestsQueue } from "../api";
import { RequestDetails } from "../owned/Requests";

/**
 * 027: the requests purchases opened, for the administrators — the most urgent first, an overdue one says
 * so. Start one, mark it done (a service's access: Portalab offers to create the account in the identity
 * provider), or decline it with a reason (the member's Coins come back).
 */
function RequestItem({ request }: { request: MarketRequest }) {
  const t = useT();
  const format = useFormat();
  const decide = useDecideRequest();
  const [note, setNote] = useState("");
  const [createAccount, setCreateAccount] = useState(true);
  const open = request.state === "pending" || request.state === "in_progress";
  return (
    <li
      className="ds-card ds-stack request-card"
      data-state={request.state}
      data-overdue={request.overdue || undefined}
    >
      <div className="request-card__head">
        <strong>{request.product_name}</strong>
        <span className="admin-muted">{request.user_name ?? t("marketplace:request.someone")}</span>
        <StatusBadge tone={request.overdue ? "bad" : request.state === "in_progress" ? "info" : "neutral"}>
          {request.overdue
            ? t("marketplace:request.overdue", { date: format.date(request.due_at, "long") })
            : t("marketplace:request.dueBy", { date: format.date(request.due_at, "long") })}
        </StatusBadge>
      </div>
      <RequestDetails request={request} />
      {request.details.outcome ? <p className="admin-muted">{String(request.details.outcome)}</p> : null}
      {open ? (
        <div className="request-card__actions">
          <label className="ds-field request-card__note">
            <span>{t("marketplace:request.note")}</span>
            <input value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} />
          </label>
          {request.kind === "service" ? (
            <label className="request-form__choice">
              <input
                type="checkbox"
                checked={createAccount}
                onChange={(e) => setCreateAccount(e.target.checked)}
              />
              {t("marketplace:request.createAccount")}
            </label>
          ) : null}
          {request.state === "pending" ? (
            <Button variant="secondary" onClick={() => decide.mutate({ id: request.id, action: "start" })}>
              <Icon name="clock" size={16} />
              {t("marketplace:request.start")}
            </Button>
          ) : null}
          <Button
            onClick={() =>
              decide.mutate({
                id: request.id,
                action: "done",
                note,
                createAccount: request.kind === "service" && createAccount,
              })
            }
            disabled={decide.isPending}
          >
            <Icon name="check" size={16} />
            {request.kind === "service" ? t("marketplace:request.approve") : t("marketplace:request.done")}
          </Button>
          <Button
            variant="ghost"
            disabled={!note.trim() || decide.isPending}
            title={note.trim() ? undefined : t("marketplace:request.declineHint")}
            onClick={() => decide.mutate({ id: request.id, action: "decline", note })}
          >
            <Icon name="close" size={16} />
            {t("marketplace:request.decline")}
          </Button>
          {decide.isError ? <p role="alert">{t("marketplace:request.failed")}</p> : null}
        </div>
      ) : (
        <p className="admin-muted">
          {t(`marketplace:request.state.${request.state}`)}
          {request.note ? ` — ${request.note}` : ""}
        </p>
      )}
    </li>
  );
}

export function RequestsQueue() {
  const t = useT();
  const [settled, setSettled] = useState(false);
  const queue = useRequestsQueue(settled);
  const items = queue.data ?? [];
  const overdue = items.filter((r) => r.overdue).length;
  return (
    <AdminSection
      title={t("marketplace:request.queue")}
      icon="inbox"
      description={
        settled
          ? t("marketplace:request.settledHint")
          : `${t("marketplace:request.queueHint", { count: items.length })}${overdue ? ` ${t("marketplace:request.overdueCount", { count: overdue })}` : ""}`
      }
      actions={
        <Button variant="ghost" onClick={() => setSettled(!settled)}>
          {settled ? t("marketplace:request.showOpen") : t("marketplace:request.showSettled")}
        </Button>
      }
    >
      {items.length ? (
        <ul className="ds-stack">
          {items.map((request) => (
            <RequestItem key={request.id} request={request} />
          ))}
        </ul>
      ) : (
        <p className="admin-muted">{t("marketplace:request.none")}</p>
      )}
    </AdminSection>
  );
}
