import { useId, useRef, useState } from "react";
import "../support.css";
import { Link, Navigate, useParams } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Card } from "../../../design-system/components/Content";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useAssistantPage } from "../../ai/pageContext";
import { useMe } from "../../auth/useAuth";
import { useTicket, useTicketActions } from "./api";
import { TicketMedia } from "./ReportMedia";
import { PriorityBadge, StateBadge, stateLabel } from "./TicketBadges";

type Line =
  | { kind: "comment"; at: string; id: string; body: string; internal: boolean; author: string | null }
  | { kind: "event"; at: string; id: string; what: string; data: Record<string, unknown> };

const EVENT_ICON: Record<string, string> = {
  created: "plus",
  transition: "chevron-right",
  assignment: "user",
  attachment_added: "link",
  incident_linked: "alert",
};

/**
 * Ticket detail (spec 016 T025, 027): the feedback it came from (its answers, a link to it), then one
 * conversation — the messages, internal notes marked for staff, and what happened in between (state
 * changes, assignment, attachments) — and the same way to act as a feedback: a slim row of actions alone,
 * or a reply that opens the composer with « Then: » (a state change, take it) on one button.
 *
 * ``team``: the team's page, in the administration's support hub (internal notes, taking it, every state
 * change); without it, the member's page — their own ticket, as they see it. A member of the team who
 * lands on someone else's ticket from the member's side is taken to the team's page.
 */
export function TicketPage({ team = false }: { team?: boolean }) {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const { ticketId = "" } = useParams();
  const me = useMe();
  const ticket = useTicket(ticketId);
  const actions = useTicketActions(ticketId);
  const [text, setText] = useState("");
  const [composing, setComposing] = useState(false);
  const [internal, setInternal] = useState(false);
  const [move, setMove] = useState<string | null>(null);
  const [takeIt, setTakeIt] = useState(false);
  const [failed, setFailed] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  // issue 171: « this ticket » for the assistant
  useAssistantPage(
    ticket.data ? `ticket id=${ticket.data.id} « ${ticket.data.title} »` : null,
    ticket.data ? `${ticket.data.reference} · ${ticket.data.title}` : null,
  );
  if (ticket.isPending) return <FunctionalState state="loading" />;
  if (ticket.isError || !ticket.data)
    return <FunctionalState state="unavailable" label={t("support:ticket.notFound")} />;
  const data = ticket.data;
  if (!team && data.staff && data.requester_id !== me.data?.id && me.data)
    return <Navigate to={`/support/queue/${data.id}`} replace />;
  const staff = team && data.staff; // the team's means, on the team's page only
  // on the member's page, only what a member may do (a member of the team finds the rest on theirs)
  const transitions = team || !data.staff ? data.transitions : [];
  const origin = data.feedback as
    | { id: string; form: string; at: string; answers: { label: string; value: string }[] }
    | null
    | undefined;
  const meId = me.data?.id;
  const canTake = staff && data.assignee_id !== meId;
  const ago = (at: string) => format.relative((Date.parse(at) - Date.now()) / 1000);
  const who = (author: string | null) =>
    author && author === meId
      ? t("support:ticket.you")
      : author && author === data.requester_id
        ? t("support:ticket.member")
        : t("support:ticket.team");
  const lines: Line[] = [
    ...data.comments.map((c) => ({
      kind: "comment" as const,
      at: c.created_at,
      id: c.id,
      body: c.body,
      internal: c.internal,
      author: c.author_id ?? null,
    })),
    ...data.history
      .filter((h) => h.kind !== "comment_added")
      .map((h) => ({
        kind: "event" as const,
        at: h.created_at,
        id: `h${h.seq}`,
        what: h.kind,
        data: h.data,
      })),
  ].sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
  const moveOf = (key: string | null) => transitions.find((tr) => String(tr.key) === key);
  const chosen = moveOf(move);
  const reset = () => {
    setText("");
    setMove(null);
    setTakeIt(false);
    setInternal(false);
    setComposing(false);
  };
  const thenLabels = [
    ...(takeIt ? [t("support:ticket.takeIt")] : []),
    ...(chosen ? [String(chosen.label)] : []),
  ];
  const sendLabel = thenLabels.length
    ? t("support:ticket.sendThen", { actions: format.list(thenLabels) })
    : internal
      ? t("support:ticket.sendNote")
      : t("support:ticket.send");
  const submit = async () => {
    const words = text.trim();
    if (!words) return;
    setFailed(false);
    try {
      if (chosen && !internal) {
        // the message travels with the state change (a change that needs one gets it)
        await actions.transition.mutateAsync({
          transition: String(chosen.key),
          comment: words,
          version: data.version,
        });
      } else {
        const after = (await (internal ? actions.note : actions.comment).mutateAsync(words)) as
          | { version?: number }
          | undefined;
        if (chosen)
          await actions.transition.mutateAsync({
            transition: String(chosen.key),
            version: after?.version ?? data.version,
          });
      }
      if (takeIt && meId) await actions.assign.mutateAsync(meId);
      reset();
    } catch {
      setFailed(true); // the message stays written, to send again
    }
  };
  const act = (key: string) => {
    const tr = moveOf(key);
    if (!tr) return;
    if (tr.comment_required) {
      // a change that needs a word: the composer opens with it chosen
      setMove(key);
      setComposing(true);
      return;
    }
    actions.transition.mutate({ transition: key, version: data.version });
  };
  return (
    <article aria-labelledby={headingId} className="support-ticket">
      <Link to={staff ? "/support/queue" : "/support"} className="support-back">
        <Icon name="chevron-left" size={16} />
        {t(staff ? "support:ticket.backQueue" : "support:ticket.back")}
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
            {!team && data.staff ? (
              <Link to={`/support/queue/${data.id}`} className="ticket-origin__link">
                {t("support:ticket.manage")}
                <Icon name="chevron-right" size={14} />
              </Link>
            ) : null}
            {data.incident_reference && data.incident_id ? (
              <Link to={`/incidents/${data.incident_id}`}>{data.incident_reference}</Link>
            ) : null}
          </span>
        }
      />
      <div className="ticket-page">
        {/* issue 354: the media the ticket is about, at its head */}
        {data.media_id ? <TicketMedia objectId={data.media_id} /> : null}
        {origin ? (
          <section className="ticket-origin" aria-label={t("support:ticket.origin")}>
            <header className="ticket-origin__head">
              <Icon name="message" size={16} />
              <span>
                {t(staff ? "support:ticket.fromFeedback" : "support:ticket.fromMyFeedback", {
                  form: origin.form,
                  when: ago(origin.at),
                })}
              </span>
              <Link to={staff ? "/support/feedback" : "/feedback"} className="ticket-origin__link">
                {t("support:ticket.seeFeedback")}
                <Icon name="chevron-right" size={14} />
              </Link>
            </header>
            <dl className="feedback-answers">
              {origin.answers.map((answer) => (
                <div key={answer.label}>
                  <dt>{answer.label}</dt>
                  <dd>{answer.value}</dd>
                </div>
              ))}
            </dl>
          </section>
        ) : data.description ? (
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
        <ol className="feedback-thread" aria-label={t("support:ticket.conversation")}>
          {lines.map((line) =>
            line.kind === "comment" ? (
              <li
                key={line.id}
                className="feedback-bubble"
                data-from={line.author && line.author === data.requester_id ? "member" : "team"}
                data-internal={line.internal || undefined}
              >
                <p>{line.body}</p>
                <span className="feedback-bubble__who">
                  {line.internal ? `${t("support:ticket.internal")} · ` : ""}
                  {who(line.author)} · {ago(line.at)}
                </span>
              </li>
            ) : (
              <li key={line.id} className="feedback-event" data-kind={line.what}>
                <Icon name={EVENT_ICON[line.what] ?? "check"} size={14} />
                <span>
                  {t(`support:history.${line.what}`)}
                  {line.what === "transition" ? ` → ${stateLabel(t, String(line.data.to))}` : ""}
                </span>
                <span className="feedback-event__when">{ago(line.at)}</span>
              </li>
            ),
          )}
        </ol>
        {data.attachments.length ? (
          <ul className="ticket-files" aria-label={t("support:ticket.attachments")}>
            {data.attachments.map((a) => (
              <li key={a.id}>
                <a href={`/api/v1/tickets/attachments/${a.id}`} className="feedback-chip">
                  <Icon name="link" size={14} />
                  {a.filename}
                  <span className="support-meta">({Math.ceil(a.size / 1024)} KB)</span>
                </a>
              </li>
            ))}
          </ul>
        ) : null}
        {actions.transition.isError && !composing ? (
          <p role="alert">{t("support:ticket.transitionFailed")}</p>
        ) : null}
        {actions.upload.isError ? <p role="alert">{t("support:ticket.attachRejected")}</p> : null}
        {composing ? (
          <form
            className="feedback-composer"
            onSubmit={(event) => {
              event.preventDefault();
              void submit();
            }}
          >
            <label htmlFor={`${headingId}-text`} className="visually-hidden">
              {t("support:ticket.comment")}
            </label>
            <textarea
              id={`${headingId}-text`}
              rows={3}
              // biome-ignore lint/a11y/noAutofocus: opened on purpose by « Write a message »
              autoFocus
              value={text}
              placeholder={t(internal ? "support:ticket.notePlaceholder" : "support:ticket.writePlaceholder")}
              onChange={(e) => setText(e.target.value)}
            />
            {staff || transitions.length ? (
              <fieldset className="feedback-then">
                <legend>{t("support:review.then")}</legend>
                {staff ? (
                  <label data-checked={internal || undefined}>
                    <input
                      type="checkbox"
                      checked={internal}
                      onChange={(e) => setInternal(e.target.checked)}
                    />
                    {internal ? <Icon name="check" size={14} /> : null}
                    {t("support:ticket.internal")}
                  </label>
                ) : null}
                {canTake ? (
                  <label data-checked={takeIt || undefined}>
                    <input type="checkbox" checked={takeIt} onChange={(e) => setTakeIt(e.target.checked)} />
                    {takeIt ? <Icon name="check" size={14} /> : null}
                    {t("support:ticket.takeIt")}
                  </label>
                ) : null}
                {transitions.map((tr) => (
                  <label key={String(tr.key)} data-checked={move === String(tr.key) || undefined}>
                    <input
                      type="checkbox"
                      checked={move === String(tr.key)}
                      onChange={() => setMove(move === String(tr.key) ? null : String(tr.key))}
                    />
                    {move === String(tr.key) ? <Icon name="check" size={14} /> : null}
                    {String(tr.label)}
                  </label>
                ))}
              </fieldset>
            ) : null}
            {failed ? <p role="alert">{t("support:ticket.sendFailed")}</p> : null}
            <div className="feedback-composer__bar">
              <Button variant="ghost" onClick={reset}>
                {t("support:reward.cancel")}
              </Button>
              <Button type="submit" disabled={!text.trim()}>
                <Icon name="send" size={16} />
                {sendLabel}
              </Button>
            </div>
          </form>
        ) : (
          <div className="feedback-actions" role="toolbar" aria-label={t("support:ticket.actions")}>
            <button type="button" className="feedback-reply-field" onClick={() => setComposing(true)}>
              <Icon name="message" size={16} />
              {t("support:ticket.writePlaceholder")}
            </button>
            <span className="feedback-chips">
              {transitions.map((tr) => (
                <button
                  key={String(tr.key)}
                  type="button"
                  className="feedback-chip"
                  onClick={() => act(String(tr.key))}
                >
                  <Icon name="chevron-right" size={14} />
                  {String(tr.label)}
                </button>
              ))}
              {canTake ? (
                <button
                  type="button"
                  className="feedback-chip"
                  onClick={() => meId && actions.assign.mutate(meId)}
                >
                  <Icon name="user" size={14} />
                  {t("support:ticket.takeIt")}
                </button>
              ) : null}
              <button type="button" className="feedback-chip" onClick={() => file.current?.click()}>
                <Icon name="plus" size={14} />
                {t("support:ticket.attach")}
              </button>
            </span>
          </div>
        )}
        <input
          ref={file}
          type="file"
          hidden
          onChange={(e) => {
            const picked = e.currentTarget.files?.[0];
            if (picked) actions.upload.mutate(picked);
          }}
        />
      </div>
    </article>
  );
}

export default TicketPage;
