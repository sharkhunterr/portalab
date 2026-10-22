import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import {
  AdminEmpty,
  AdminPage,
  AdminSection,
  AdminTabs,
  StatusBadge,
} from "../../../design-system/admin/AdminKit";
import { Avatar } from "../../../design-system/components/Avatar";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type FormRow as DefinedForm, FormEditor } from "../admin/Definitions";
import type { FieldDef } from "../tickets/api";
import { useFeedbackActions, useFeedbackDetail } from "../tickets/api";
import { optionLabel } from "../tickets/FieldInputs";
import { FeedbackReward, useCanReward } from "./FeedbackReward";
import "../support.css";

type Item = components["schemas"]["FeedbackOut"];
type Results = components["schemas"]["FeedbackResultsOut"];
type FormRow = DefinedForm;

const QUEUE = ["support", "feedback"] as const;
const STATUSES = ["new", "reviewed", "converted", "dismissed", "all"] as const;
const TONE: Record<string, "info" | "ok" | "neutral"> = {
  new: "info",
  reviewed: "ok",
  converted: "ok",
  dismissed: "neutral",
};

/** Everyone's feedback, or one member's (their admin card). */
function useQueue(userId?: string) {
  return useQuery({
    queryKey: [...QUEUE, userId ?? null],
    retry: false,
    queryFn: async () => {
      const data = (
        await api.GET("/api/v1/support/feedback", { params: { query: userId ? { user_id: userId } : {} } })
      ).data;
      return (Array.isArray(data) ? data : []) as Item[];
    },
  });
}

function useForms() {
  return useQuery({
    queryKey: ["support", "admin", "forms"],
    retry: false,
    queryFn: async () => {
      const data = (await api.GET("/api/v1/admin/support/forms")).data;
      return (Array.isArray(data) ? data : []) as unknown as FormRow[];
    },
  });
}

function Stars({ value }: { value: number }) {
  const t = useT();
  return (
    <span className="stars" role="img" aria-label={t("support:rating.value", { value })}>
      {[1, 2, 3, 4, 5].map((star) => (
        <span key={star} data-on={star <= value || undefined} aria-hidden="true">
          <Icon name="star" size={14} />
        </span>
      ))}
    </span>
  );
}

/** The answers in the form's own words (labels, choices), ratings as stars. */
export function Answers({ payload, fields }: { payload: Record<string, unknown>; fields: FieldDef[] }) {
  const t = useT();
  const known = new Map(fields.map((f) => [f.key, f]));
  return (
    <dl className="feedback-answers">
      {Object.entries(payload).map(([key, value]) => {
        const field = known.get(key);
        let shown: React.ReactNode = String(value);
        if (field?.type === "rating" && typeof value === "number") shown = <Stars value={value} />;
        else if (Array.isArray(value)) shown = value.map((v) => optionLabel(t, String(v))).join(", ");
        else if (typeof value === "boolean") shown = value ? t("support:answer.yes") : t("support:answer.no");
        else if (field?.type === "select") shown = optionLabel(t, String(value));
        return (
          <div key={key}>
            <dt>{field?.label ?? key}</dt>
            <dd>{shown}</dd>
          </div>
        );
      })}
    </dl>
  );
}

const EVENT_ICON: Record<string, string> = {
  read: "check",
  closed: "inbox",
  reopened: "undo",
  rewarded: "gift",
  converted: "ticket",
};
const TOOL_ICON: Record<string, string> = {
  ticket: "ticket",
  feature_proposal: "lightbulb",
  community_project: "users",
};
type Then = "close" | "reward" | "ticket" | "feature_proposal" | "community_project";
const CONVERSIONS: readonly Then[] = ["ticket", "feature_proposal", "community_project"];

/**
 * One feedback (027): the conversation (the member's answers, the team's reply), then two ways to handle
 * it. Without writing, a slim row of actions does just that (read, close, reward, a ticket, a proposal, a
 * project). Touching « Reply » opens the composer: the reply, and what to do once it is sent — any of
 * close, reward, make a ticket… (closing and a conversion exclude each other: a conversion files it
 * already) — on one button (« Send, close and reward »).
 */
function Detail({ item, fields }: { item: Item; fields: FieldDef[] }) {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const detail = useFeedbackDetail(item.id);
  const { convert, review } = useFeedbackActions(item.id);
  const canReward = useCanReward(item);
  const [reply, setReply] = useState("");
  const [composing, setComposing] = useState(false);
  const [chosen, setChosen] = useState<Then[]>([]);
  const [after, setAfter] = useState<Then[]>([]); // what waits for the reward to be given
  const [rewarding, setRewarding] = useState<{ message: string } | null>(null);
  const [pending, setPending] = useState<{ target: string; token: string } | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  // the contribution is left out: a reward says thank you better, in the currency or XP the admin picks
  const conversions = (detail.data?.conversions ?? []).filter((c) => c.target !== "contribution");
  const closed = item.status === "dismissed";
  const name = item.submitter_name ?? t("support:review.someone");
  const refresh = () =>
    Promise.all([
      client.invalidateQueries({ queryKey: [...QUEUE] }),
      client.invalidateQueries({ queryKey: ["support", "feedback", item.id] }),
    ]);
  const ago = (at: string) => format.relative((Date.parse(at) - Date.now()) / 1000);
  // the history; a reply written before it was kept (or its part not in it) shows first, as it was
  const kept = detail.data?.history ?? [];
  let earlier = item.reply ?? "";
  for (const event of kept) if (event.kind === "replied") earlier = earlier.replace(event.text ?? "", "");
  earlier = earlier.trim();
  const history = [
    ...(earlier
      ? [{ kind: "replied", text: earlier, detail: {}, at: item.replied_at ?? item.created_at }]
      : []),
    ...kept,
  ];
  const eventText = (event: (typeof history)[number]) => {
    const detail = (event.detail ?? {}) as Record<string, string | number | undefined>;
    if (event.kind === "rewarded") return t("support:history.rewarded", { what: String(detail.label ?? "") });
    if (event.kind === "converted")
      return t(`support:history.converted.${String(detail.target ?? "ticket")}`, {
        label: String(detail.label ?? ""),
      });
    return t(`support:history.${event.kind}`);
  };
  const toggle = (key: Then) =>
    setChosen((current) => {
      if (current.includes(key)) return current.filter((k) => k !== key);
      const kept =
        key === "close"
          ? current.filter((k) => !CONVERSIONS.includes(k))
          : CONVERSIONS.includes(key)
            ? current.filter((k) => k !== "close")
            : current;
      return [...kept, key];
    });
  const run = async (actions: Then[]) => {
    if (actions.includes("close")) review.mutate("dismiss");
    for (const target of actions.filter((k) => CONVERSIONS.includes(k))) {
      try {
        await convert.mutateAsync({ target });
      } catch (error) {
        const token =
          error instanceof ApiError ? (error.extensions.confirmation as string | undefined) : undefined;
        if (token) {
          setPending({ target, token }); // confirmed in place, the others wait for another time
          return;
        }
      }
    }
  };
  const start = (target: string) =>
    convert.mutate(
      { target },
      {
        onSuccess: () => setDone(t("support:review.converted")),
        onError: (error) => {
          const token =
            error instanceof ApiError ? (error.extensions.confirmation as string | undefined) : undefined;
          if (token) setPending({ target, token });
        },
      },
    );
  const send = useMutation({
    mutationFn: async (text: string) =>
      (
        await api.POST("/api/v1/support/feedback/{feedback_id}/reply", {
          params: { path: { feedback_id: item.id } },
          // the earlier reply stays: the new one follows it (the member keeps the whole exchange)
          body: { text, append: true },
        })
      ).data,
  });
  const reset = () => {
    setReply("");
    setChosen([]);
    setComposing(false);
  };
  const submit = async () => {
    const text = reply.trim();
    if (!text) return;
    if (chosen.includes("reward")) {
      // the reward's dialog sends the reply with its thank-you: one message, one notification; the
      // other actions follow once it is given
      setAfter(chosen.filter((k) => k !== "reward"));
      setRewarding({ message: text });
      return;
    }
    setFailed(false);
    try {
      await send.mutateAsync(text);
    } catch {
      setFailed(true); // the reply stays written, to send again
      return;
    }
    await run(chosen);
    setDone(t("support:review.replied"));
    reset();
    void refresh();
  };
  const label = (key: Then) => t(`support:review.thenAction.${key}`);
  const sendLabel =
    chosen.length === 0
      ? t("support:review.send")
      : chosen.length === 1
        ? t("support:review.sendAnd", { action: label(chosen[0] as Then) })
        : t("support:review.sendList", { actions: format.list(chosen.map(label)) });
  const thens: Then[] = [
    ...(closed ? [] : (["close"] as const)),
    ...(canReward ? (["reward"] as const) : []),
    ...conversions.filter((c) => c.available && !c.done).map((c) => c.target as Then),
  ];
  return (
    <div className="feedback-detail">
      <ol className="feedback-thread" aria-label={t("support:review.conversation")}>
        <li className="feedback-bubble" data-from="member">
          <Answers payload={item.payload} fields={fields} />
        </li>
        {history.map((event, index) =>
          event.kind === "replied" ? (
            // biome-ignore lint/suspicious/noArrayIndexKey: a history line has no identity of its own
            <li key={index} className="feedback-bubble" data-from="team">
              <p>{event.text}</p>
              <span className="feedback-bubble__who">
                {t("support:review.team")} · {ago(event.at)}
              </span>
            </li>
          ) : (
            // biome-ignore lint/suspicious/noArrayIndexKey: a history line has no identity of its own
            <li key={index} className="feedback-event" data-kind={event.kind}>
              <Icon name={EVENT_ICON[event.kind] ?? "check"} size={14} />
              <span>{eventText(event)}</span>
              <span className="feedback-event__when">{ago(event.at)}</span>
            </li>
          ),
        )}
      </ol>
      {detail.isError ? <p role="alert">{t("support:review.detailFailed")}</p> : null}
      {done ? (
        <p role="status" className="feedback-done">
          {done}
        </p>
      ) : null}
      {pending ? (
        <div role="alertdialog" aria-label={t("support:convert.confirm")} className="feedback-confirm">
          <p>{t("support:convert.confirm")}</p>
          <div className="feedback-confirm__actions">
            <Button variant="ghost" onClick={() => setPending(null)}>
              {t("support:reward.cancel")}
            </Button>
            <Button
              onClick={() =>
                convert.mutate(
                  { target: pending.target, confirmation: pending.token },
                  { onSuccess: () => setPending(null) },
                )
              }
            >
              {t("support:convert.yes")}
            </Button>
          </div>
        </div>
      ) : null}
      {canReward ? (
        <FeedbackReward
          item={item}
          trigger={null}
          open={rewarding !== null}
          onOpenChange={(next) => setRewarding(next ? (rewarding ?? { message: "" }) : null)}
          message={rewarding?.message ?? ""}
          onDone={() => {
            setDone(t("support:reward.done"));
            void run(after);
            setAfter([]);
            reset();
            void refresh();
          }}
        />
      ) : null}
      {composing ? (
        <form
          className="feedback-composer"
          data-open=""
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <label htmlFor={`reply-${item.id}`} className="visually-hidden">
            {t("support:review.replyTo", { name })}
          </label>
          <textarea
            id={`reply-${item.id}`}
            rows={3}
            // biome-ignore lint/a11y/noAutofocus: opened on purpose by « Reply »
            autoFocus
            value={reply}
            placeholder={t("support:review.replyTo", { name })}
            onChange={(e) => setReply(e.target.value)}
          />
          <fieldset className="feedback-then">
            <legend>{t("support:review.then")}</legend>
            {thens.map((key) => (
              <label key={key} data-checked={chosen.includes(key) || undefined}>
                <input type="checkbox" checked={chosen.includes(key)} onChange={() => toggle(key)} />
                {chosen.includes(key) ? <Icon name="check" size={14} /> : null}
                {t(`support:review.thenOption.${key}`)}
              </label>
            ))}
          </fieldset>
          {failed ? <p role="alert">{t("support:review.sendFailed")}</p> : null}
          <div className="feedback-composer__bar">
            <Button variant="ghost" onClick={reset}>
              {t("support:reward.cancel")}
            </Button>
            <Button type="submit" disabled={!reply.trim() || send.isPending}>
              <Icon name="send" size={16} />
              {sendLabel}
            </Button>
          </div>
        </form>
      ) : (
        <div className="feedback-actions" role="toolbar" aria-label={t("support:review.tools")}>
          <button type="button" className="feedback-reply" onClick={() => setComposing(true)}>
            <Icon name="message" size={16} />
            {item.reply ? t("support:review.replyAgain") : t("support:review.replyTo", { name })}
          </button>
          <span className="feedback-chips">
            {closed ? (
              <button type="button" className="feedback-chip" onClick={() => review.mutate("review")}>
                <Icon name="undo" size={14} />
                {t("support:review.tool.reopen")}
              </button>
            ) : (
              <>
                {item.status === "new" ? (
                  <button type="button" className="feedback-chip" onClick={() => review.mutate("review")}>
                    <Icon name="check" size={14} />
                    {t("support:review.tool.read")}
                  </button>
                ) : null}
                <button type="button" className="feedback-chip" onClick={() => review.mutate("dismiss")}>
                  <Icon name="inbox" size={14} />
                  {t(item.status === "new" ? "support:review.tool.readClose" : "support:review.tool.close")}
                </button>
              </>
            )}
            {canReward ? (
              <button
                type="button"
                className="feedback-chip"
                data-tone="reward"
                onClick={() => setRewarding({ message: "" })}
              >
                <Icon name="gift" size={14} />
                {t("support:review.tool.reward")}
              </button>
            ) : null}
            {conversions.map((c) => (
              <button
                key={c.target}
                type="button"
                className="feedback-chip"
                disabled={!c.available || Boolean(c.done)}
                title={c.reason ? t(`support:convert.reason.${c.reason}`) : undefined}
                onClick={() => start(c.target)}
              >
                <Icon name={c.done ? "check" : (TOOL_ICON[c.target] ?? "sparkles")} size={14} />
                {t(`support:review.tool.${c.target}`)}
                {c.reason ? (
                  <span className="visually-hidden"> ({t(`support:convert.reason.${c.reason}`)})</span>
                ) : null}
              </button>
            ))}
          </span>
        </div>
      )}
    </div>
  );
}

function ResultsPanel({ form }: { form: FormRow }) {
  const t = useT();
  const format = useFormat();
  const results = useQuery({
    queryKey: ["support", "feedback-results", form.key],
    queryFn: async () =>
      (
        await api.GET("/api/v1/support/feedback/results/{form_key}", {
          params: { path: { form_key: form.key } },
        })
      ).data as Results,
  });
  if (!results.data) return <FunctionalState state="loading" />;
  return (
    <div className="feedback-results">
      <p className="feedback-results__total">{t("support:review.answers", { count: results.data.total })}</p>
      {results.data.fields.map((field) => {
        const counts = field.counts ?? {};
        const most = Math.max(1, ...Object.values(counts));
        return (
          <div key={field.key} className="feedback-result">
            <strong>{field.label}</strong>
            {field.average !== null && field.average !== undefined ? (
              <span className="feedback-result__average">
                {field.type === "rating" ? <Stars value={Math.round(field.average)} /> : null}{" "}
                {t("support:review.average", { value: format.number(field.average) })}
              </span>
            ) : null}
            {Object.keys(counts).length ? (
              <ul className="feedback-bars">
                {Object.entries(counts).map(([choice, count]) => (
                  <li key={choice}>
                    <span>{field.type === "rating" ? `${choice} ★` : optionLabel(t, choice)}</span>
                    <span className="feedback-bars__bar" aria-hidden="true">
                      <span style={{ inlineSize: `${Math.round((count / most) * 100)}%` }} />
                    </span>
                    <strong>{count}</strong>
                  </li>
                ))}
              </ul>
            ) : null}
            {field.latest?.length ? (
              <ul className="feedback-quotes">
                {field.latest.slice(0, 6).map((text, i) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: answers have no identity of their own
                  <li key={i}>« {text} »</li>
                ))}
              </ul>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

/** One card per feedback — who, which form, an excerpt, its status — opened to its detail. */
function FeedbackCards({ items, fieldsOf }: { items: Item[]; fieldsOf: (key: string) => FieldDef[] }) {
  const t = useT();
  const format = useFormat();
  const [open, setOpen] = useState<string | null>(null);
  return (
    <ul className="feedback-queue">
      {items.map((item) => {
        const first = Object.values(item.payload).find((v) => typeof v === "string") as string | undefined;
        const expanded = open === item.id;
        return (
          <li key={item.id} className="feedback-card" data-status={item.status}>
            <button
              type="button"
              className="feedback-card__head"
              aria-expanded={expanded}
              onClick={() => setOpen(expanded ? null : item.id)}
            >
              <Avatar
                name={item.submitter_name ?? "?"}
                userId={item.submitter_id ?? undefined}
                size="sm"
                decorative
              />
              <span className="feedback-card__text">
                <span className="feedback-card__who">
                  <strong>{item.submitter_name ?? t("support:review.someone")}</strong>
                  <span className="admin-muted">
                    {item.form_label ?? item.form_key} ·{" "}
                    {format.relative((Date.parse(item.created_at) - Date.now()) / 1000)}
                  </span>
                </span>
                {first ? <span className="feedback-card__excerpt">{first}</span> : null}
              </span>
              <span className="feedback-card__badges">
                {item.reply ? (
                  <span className="admin-muted" title={t("support:review.replied")}>
                    <Icon name="message" size={14} />
                  </span>
                ) : null}
                <StatusBadge tone={TONE[item.status] ?? "neutral"}>
                  {t(`support:feedback.status.${item.status}`)}
                </StatusBadge>
                <Icon name={expanded ? "chevron-down" : "chevron-right"} size={16} />
              </span>
            </button>
            {expanded ? <Detail item={item} fields={fieldsOf(item.form_key)} /> : null}
          </li>
        );
      })}
    </ul>
  );
}

/** One member's feedback (their admin card), the same cards as the review queue. */
export function MemberFeedback({ userId }: { userId: string }) {
  const t = useT();
  const queue = useQueue(userId);
  const forms = useForms();
  const fieldsOf = (key: string) => (forms.data ?? []).find((f) => f.key === key)?.fields ?? [];
  if (queue.isError) return <FunctionalState state="unauthorized" />;
  if (queue.data && !queue.data.length) return <AdminEmpty icon="inbox" title={t("support:review.empty")} />;
  return <FeedbackCards items={queue.data ?? []} fieldsOf={fieldsOf} />;
}

type Phase = "open" | "planned" | "ended";
const DAY = 86_400_000;

function phaseOf(form: FormRow, now: number): Phase {
  const opens = form.opens_at ? Date.parse(form.opens_at) : 0;
  const closes = form.closes_at ? Date.parse(form.closes_at) : Number.POSITIVE_INFINITY;
  if (!form.enabled || now >= closes) return "ended";
  return now < opens ? "planned" : "open";
}

/** One request to the members: its period, how far it has gone, its answers summed up or one by one. */
function RequestCard({ form, answers }: { form: FormRow; answers: Item[] }) {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const [view, setView] = useState<"summary" | "answers">("summary");
  const [editing, setEditing] = useState(false);
  const now = Date.now();
  const phase = phaseOf(form, now);
  const opens = form.opens_at ? Date.parse(form.opens_at) : now;
  const closes = form.closes_at ? Date.parse(form.closes_at) : null;
  const elapsed = closes && closes > opens ? Math.min(1, Math.max(0, (now - opens) / (closes - opens))) : 0;
  const waiting = answers.filter((a) => a.status === "new").length;
  const latest = answers.reduce((max, a) => Math.max(max, Date.parse(a.created_at)), 0);
  const when =
    phase === "planned"
      ? t("support:requests.startsIn", { days: Math.max(1, Math.ceil((opens - now) / DAY)) })
      : phase === "open" && closes
        ? t("support:requests.endsIn", { days: Math.max(1, Math.ceil((closes - now) / DAY)) })
        : phase === "ended" && closes
          ? t("support:requests.endedOn", { date: format.date(new Date(closes).toISOString(), "medium") })
          : t("support:requests.noEnd");
  const closeNow = useMutation({
    mutationFn: async () =>
      api.PUT("/api/v1/admin/support/forms/{key}", {
        params: { path: { key: form.key } },
        body: {
          kind: form.kind,
          label: form.label,
          enabled: form.enabled,
          description: form.description ?? "",
          icon: form.icon ?? null,
          requested: true,
          fields: form.fields as unknown as Array<Record<string, unknown>>,
          opens_at: form.opens_at ?? null,
          closes_at: new Date().toISOString(),
        },
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["support"] }),
  });
  return (
    <li className="request-card" data-phase={phase}>
      <header className="request-card__head">
        <span className="request-card__icon" aria-hidden="true">
          <Icon name={form.icon ?? "message"} size={22} />
        </span>
        <span className="request-card__title">
          <strong>{form.label}</strong>
          <span className="admin-muted">{when}</span>
        </span>
        <StatusBadge tone={phase === "open" ? "ok" : phase === "planned" ? "info" : "neutral"}>
          {t(`support:requests.phase.${phase}`)}
        </StatusBadge>
      </header>
      {phase === "open" && closes ? (
        <span className="request-card__time" aria-hidden="true">
          <span style={{ inlineSize: `${Math.round(elapsed * 100)}%` }} />
        </span>
      ) : null}
      <p className="request-card__figures">
        <span>{t("support:requests.answerCount", { count: answers.length })}</span>
        {waiting ? (
          <span data-tone="waiting">{t("support:requests.waiting", { count: waiting })}</span>
        ) : null}
        {latest ? (
          <span>{t("support:requests.latestWhen", { when: format.relative((latest - now) / 1000) })}</span>
        ) : null}
      </p>
      <div className="request-card__bar">
        <fieldset className="request-card__views">
          <legend className="visually-hidden">{form.label}</legend>
          {(["summary", "answers"] as const).map((key) => (
            <button key={key} type="button" aria-pressed={view === key} onClick={() => setView(key)}>
              {key === "answers"
                ? t("support:requests.view.answers", { count: answers.length })
                : t("support:requests.view.summary")}
            </button>
          ))}
        </fieldset>
        <span className="request-card__actions">
          <Dialog
            open={editing}
            onOpenChange={setEditing}
            title={form.label}
            closeLabel={t("support:admin.close")}
            size="lg"
            trigger={
              <Button variant="ghost">
                <Icon name="settings" size={16} />
                {t("support:requests.edit")}
              </Button>
            }
          >
            <FormEditor form={form} onDone={() => setEditing(false)} />
          </Dialog>
          {phase === "open" ? (
            <Button variant="ghost" disabled={closeNow.isPending} onClick={() => closeNow.mutate()}>
              <Icon name="close" size={16} />
              {t("support:requests.closeNow")}
            </Button>
          ) : null}
        </span>
      </div>
      {view === "summary" ? (
        <ResultsPanel form={form} />
      ) : answers.length ? (
        <FeedbackCards items={answers} fieldsOf={() => form.fields} />
      ) : (
        <p className="admin-muted">{t("support:review.answers", { count: 0 })}</p>
      )}
    </li>
  );
}

/**
 * The requests: forms the administrators send the members for a while (027) — created here, each one a
 * card with its period and progress, its answers summed up or handled one by one (read, reward, convert).
 */
function RequestsPanel({ forms, items }: { forms: FormRow[]; items: Item[] }) {
  const t = useT();
  const [creating, setCreating] = useState(false);
  const now = Date.now();
  const [phase, setPhase] = useState<Phase>("open");
  const shown = forms.filter((f) => phaseOf(f, now) === phase);
  const count = (p: Phase) => forms.filter((f) => phaseOf(f, now) === p).length;
  return (
    <AdminSection
      span="full"
      icon="star"
      title={t("support:requests.title")}
      description={t("support:requests.hint")}
      actions={
        <Dialog
          open={creating}
          onOpenChange={setCreating}
          title={t("support:forms.new")}
          closeLabel={t("support:admin.close")}
          size="lg"
          trigger={
            <Button>
              <Icon name="plus" size={16} />
              {t("support:requests.new")}
            </Button>
          }
        >
          <FormEditor onDone={() => setCreating(false)} />
        </Dialog>
      }
    >
      <fieldset className="request-phases">
        <legend className="visually-hidden">{t("support:requests.title")}</legend>
        {(["open", "planned", "ended"] as const).map((p) => (
          <button key={p} type="button" aria-pressed={phase === p} onClick={() => setPhase(p)}>
            {t(`support:requests.phase.${p}`)} <span className="request-phases__count">{count(p)}</span>
          </button>
        ))}
      </fieldset>
      {shown.length ? (
        <ul className="request-cards">
          {shown.map((form) => (
            <RequestCard key={form.key} form={form} answers={items.filter((i) => i.form_key === form.key)} />
          ))}
        </ul>
      ) : (
        <AdminEmpty icon="star" title={t(`support:requests.none.${phase}`)} />
      )}
    </AdminSection>
  );
}

/**
 * Feedback review (spec 016 T030/T032; 027 redesign, staff): by status, one card per feedback — who, which
 * form, the answers in words — opened to reply (the member is notified), mark as read, dismiss or convert;
 * the **requests** tab sums each request's answers up (average ratings, choices, latest comments).
 */
export function ReviewQueue() {
  const t = useT();
  const queue = useQueue();
  const forms = useForms();
  const [status, setStatus] = useState<(typeof STATUSES)[number] | "requests">("new");
  const items = queue.data ?? [];
  const fieldsOf = (key: string) => (forms.data ?? []).find((f) => f.key === key)?.fields ?? [];
  const shown = items.filter((i) => status === "all" || i.status === status);
  const requested = (forms.data ?? []).filter((f) => f.requested);
  return (
    <AdminPage
      icon="message"
      title={t("support:review.title")}
      description={t("support:review.subtitle")}
      tabs={
        <AdminTabs
          label={t("support:review.title")}
          current={status}
          onChange={(next) => setStatus(next as typeof status)}
          tabs={[
            ...STATUSES.map((s) => ({
              key: s,
              label: t(`support:review.tabs.${s}`),
              count: s === "all" ? items.length : items.filter((i) => i.status === s).length,
            })),
            {
              key: "requests",
              label: t("support:review.tabs.requests"),
              count: requested.filter((f) => phaseOf(f, Date.now()) === "open").length,
            },
          ]}
        />
      }
    >
      {queue.isError ? <FunctionalState state="unauthorized" /> : null}
      {status === "requests" ? (
        <RequestsPanel forms={requested} items={items} />
      ) : (
        <>
          {queue.data && !shown.length ? <AdminEmpty icon="inbox" title={t("support:review.empty")} /> : null}
          <FeedbackCards items={shown} fieldsOf={fieldsOf} />
        </>
      )}
    </AdminPage>
  );
}

export default ReviewQueue;
