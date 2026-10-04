import { type FormEvent, useId, useRef, useState } from "react";
import "../support.css";
import { Link, useParams } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useMe } from "../../auth/useAuth";
import { useTicket, useTicketActions } from "./api";

/**
 * Ticket detail (spec 016 T025): state and workflow actions offered by the server, fields, the
 * conversation (internal notes marked for staff), attachments (download, upload) and the timeline.
 */
export function TicketPage() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const { ticketId = "" } = useParams();
  const me = useMe();
  const ticket = useTicket(ticketId);
  const actions = useTicketActions(ticketId);
  const [comment, setComment] = useState("");
  const [internal, setInternal] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  if (ticket.isPending) return <FunctionalState state="loading" />;
  if (ticket.isError || !ticket.data)
    return <FunctionalState state="unavailable" label={t("support:ticket.notFound")} />;
  const data = ticket.data;
  const send = (event: FormEvent) => {
    event.preventDefault();
    const action = internal ? actions.note : actions.comment;
    action.mutate(comment, { onSuccess: () => setComment("") });
  };
  return (
    <article aria-labelledby={headingId} className="support-ticket">
      <PageHeader titleId={headingId} level={2} icon="ticket" title={`${data.reference} · ${data.title}`} />
      <p>
        {t("support:ticket.state")}: <strong>{data.state_label}</strong> · {t("support:ticket.priority")}:{" "}
        {data.priority}
        {data.incident_reference && data.incident_id ? (
          <>
            {" "}
            · <Link to={`/incidents/${data.incident_id}`}>{data.incident_reference}</Link>
          </>
        ) : null}
      </p>
      <fieldset className="ds-stack ds-stack--row support-actions">
        <legend className="visually-hidden">{t("support:ticket.actions")}</legend>
        {data.transitions.map((tr) => (
          <Button
            key={String(tr.key)}
            variant="secondary"
            onClick={() =>
              actions.transition.mutate({
                transition: String(tr.key),
                ...(tr.comment_required ? { comment } : {}),
                version: data.version,
              })
            }
            disabled={Boolean(tr.comment_required) && !comment.trim()}
          >
            {String(tr.label)}
          </Button>
        ))}
        {data.staff && data.assignee_id !== me.data?.id ? (
          <Button variant="secondary" onClick={() => actions.assign.mutate(me.data?.id ?? null)}>
            {t("support:ticket.takeIt")}
          </Button>
        ) : null}
      </fieldset>
      {actions.transition.isError ? <p role="alert">{t("support:ticket.transitionFailed")}</p> : null}
      {data.description ? <p className="support-ticket__description">{data.description}</p> : null}
      {Object.keys(data.fields).length ? (
        <dl>
          {data.field_defs
            .filter((d) => String(d.key) in data.fields)
            .map((d) => (
              <div key={String(d.key)}>
                <dt>{String(d.label)}</dt>
                <dd>{String(data.fields[String(d.key)])}</dd>
              </div>
            ))}
        </dl>
      ) : null}
      <h3>{t("support:ticket.conversation")}</h3>
      <ol className="support-thread">
        {data.comments.map((c) => (
          <li key={c.id} data-internal={c.internal}>
            {c.internal ? <strong>{t("support:ticket.internal")} · </strong> : null}
            <span className="support-meta">{format.dateTime(c.created_at)}</span>
            <p>{c.body}</p>
          </li>
        ))}
      </ol>
      <form onSubmit={send}>
        <div className="ds-field">
          <label htmlFor={`${headingId}-comment`}>{t("support:ticket.comment")}</label>
          <textarea
            id={`${headingId}-comment`}
            rows={3}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
        </div>
        {data.staff ? (
          <label>
            <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} />{" "}
            {t("support:ticket.asInternal")}
          </label>
        ) : null}
        <Button type="submit" disabled={!comment.trim()}>
          {t("support:ticket.send")}
        </Button>
      </form>
      <h3>{t("support:ticket.attachments")}</h3>
      <ul>
        {data.attachments.map((a) => (
          <li key={a.id}>
            <a href={`/api/v1/tickets/attachments/${a.id}`}>{a.filename}</a> ({Math.ceil(a.size / 1024)} KB)
          </li>
        ))}
      </ul>
      <Button variant="secondary" onClick={() => file.current?.click()}>
        {t("support:ticket.attach")}
      </Button>
      <input
        ref={file}
        type="file"
        hidden
        onChange={(e) => {
          const chosen = e.currentTarget.files?.[0];
          if (chosen) actions.upload.mutate(chosen);
        }}
      />
      {actions.upload.isError ? <p role="alert">{t("support:ticket.attachRejected")}</p> : null}
      <h3>{t("support:ticket.history")}</h3>
      <ol className="support-history">
        {data.history.map((h) => (
          <li key={h.seq}>
            {format.dateTime(h.created_at)} · {t(`support:history.${h.kind}`)}
            {h.kind === "transition" ? ` → ${String(h.data.to)}` : ""}
          </li>
        ))}
      </ol>
    </article>
  );
}

export default TicketPage;
