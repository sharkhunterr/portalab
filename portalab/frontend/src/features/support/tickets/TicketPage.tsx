import { type FormEvent, useId, useRef, useState } from "react";
import "../support.css";
import { Link, useParams } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Card } from "../../../design-system/components/Content";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useMe } from "../../auth/useAuth";
import { useTicket, useTicketActions } from "./api";
import { PriorityBadge, StateBadge, stateLabel } from "./TicketBadges";

/**
 * Ticket detail (spec 016 T025, 027 T095): state and priority badges, then the description and the
 * conversation (own messages on one side, internal notes marked for staff) next to a side column with the
 * workflow actions offered by the server, attachments (download, upload) and the timeline.
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
  const mine = (authorId: string | null | undefined) => Boolean(authorId) && authorId === me.data?.id;
  return (
    <article aria-labelledby={headingId} className="support-ticket">
      <Link to="/support" className="support-back">
        <Icon name="chevron-left" size={16} />
        {t("support:ticket.back")}
      </Link>
      <PageHeader
        titleId={headingId}
        level={2}
        icon="ticket"
        title={data.title}
        context={
          <span className="support-ticket__context">
            <span className="support-card__ref">{data.reference}</span>
            <StateBadge state={data.state} label={data.state_label} />
            <PriorityBadge priority={data.priority} />
            {data.incident_reference && data.incident_id ? (
              <Link to={`/incidents/${data.incident_id}`}>{data.incident_reference}</Link>
            ) : null}
          </span>
        }
      />
      <div className="support-ticket__layout">
        <div className="support-ticket__main">
          {data.description ? (
            <Card className="support-ticket__description">
              <p>{data.description}</p>
              {Object.keys(data.fields).length ? (
                <dl className="support-fields">
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
            </Card>
          ) : null}
          <h3>{t("support:ticket.conversation")}</h3>
          {data.comments.length === 0 ? (
            <p className="support-meta">{t("support:ticket.noComment")}</p>
          ) : null}
          <ol className="support-thread">
            {data.comments.map((c) => (
              <li key={c.id} data-internal={c.internal} data-mine={mine(c.author_id)}>
                <span className="support-thread__who">
                  {c.internal ? `${t("support:ticket.internal")} · ` : null}
                  {mine(c.author_id) ? t("support:ticket.you") : t("support:ticket.team")}
                  <span className="support-meta"> · {format.dateTime(c.created_at)}</span>
                </span>
                <p>{c.body}</p>
              </li>
            ))}
          </ol>
          <form onSubmit={send} className="support-reply">
            <div className="ds-field">
              <label htmlFor={`${headingId}-comment`}>{t("support:ticket.comment")}</label>
              <textarea
                id={`${headingId}-comment`}
                rows={3}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
            </div>
            <div className="support-reply__actions">
              {data.staff ? (
                <label>
                  <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} />{" "}
                  {t("support:ticket.asInternal")}
                </label>
              ) : null}
              <Button type="submit" disabled={!comment.trim()}>
                <Icon name="message" size={16} />
                {t("support:ticket.send")}
              </Button>
            </div>
          </form>
        </div>
        <aside className="support-ticket__side" aria-label={t("support:ticket.details")}>
          {data.transitions.length || (data.staff && data.assignee_id !== me.data?.id) ? (
            <Card title={t("support:ticket.actions")} icon="zap">
              <fieldset className="support-actions">
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
            </Card>
          ) : null}
          <Card title={t("support:ticket.attachments")} icon="link">
            {data.attachments.length ? (
              <ul className="support-attachments">
                {data.attachments.map((a) => (
                  <li key={a.id}>
                    <a href={`/api/v1/tickets/attachments/${a.id}`}>{a.filename}</a>{" "}
                    <span className="support-meta">({Math.ceil(a.size / 1024)} KB)</span>
                  </li>
                ))}
              </ul>
            ) : null}
            <Button variant="secondary" onClick={() => file.current?.click()}>
              <Icon name="plus" size={16} />
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
          </Card>
          <Card title={t("support:ticket.history")} icon="clock">
            <ol className="support-history">
              {data.history.map((h) => (
                <li key={h.seq}>
                  <span>
                    {t(`support:history.${h.kind}`)}
                    {h.kind === "transition" ? ` → ${stateLabel(t, String(h.data.to))}` : ""}
                  </span>
                  <span className="support-meta">{format.dateTime(h.created_at)}</span>
                </li>
              ))}
            </ol>
          </Card>
        </aside>
      </div>
    </article>
  );
}

export default TicketPage;
