import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import type { FieldDef } from "../tickets/api";
import { FieldInputs } from "../tickets/FieldInputs";
import "../support.css";

type Form = components["schemas"]["FeedbackFormOut"];
type Request = components["schemas"]["FeedbackRequestOut"];
type Mine = components["schemas"]["FeedbackOut"];

const KIND_ICONS: Record<string, string> = {
  general: "message",
  bug_report: "bug",
  feature_request: "lightbulb",
  survey: "star",
};
const KEY = ["support", "feedback-me"] as const;

function useForms() {
  return useQuery({
    queryKey: [...KEY, "forms"],
    queryFn: async () => ((await api.GET("/api/v1/feedback/forms")).data ?? []) as Form[],
  });
}

function useRequests() {
  return useQuery({
    queryKey: [...KEY, "requests"],
    queryFn: async () => ((await api.GET("/api/v1/me/feedback/requests")).data ?? []) as Request[],
  });
}

function useMine() {
  return useQuery({
    queryKey: [...KEY, "mine"],
    queryFn: async () => ((await api.GET("/api/v1/me/feedback")).data ?? []) as Mine[],
  });
}

/** One form filled in place; on success it says thank you and the lists refresh. */
function Answer({ form, onDone }: { form: Form; onDone: () => void }) {
  const t = useT();
  const client = useQueryClient();
  const [values, setValues] = useState<Record<string, unknown>>({});
  const submit = useMutation({
    mutationFn: async () =>
      (await api.POST("/api/v1/feedback", { body: { form_key: form.key, values } })).data,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: KEY });
      onDone();
    },
  });
  const invalid =
    submit.error instanceof ApiError ? ((submit.error.extensions.fields as string[] | undefined) ?? []) : [];
  return (
    <form
      className="feedback-answer"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        submit.mutate();
      }}
    >
      {form.description ? <p className="feedback-answer__intro">{form.description}</p> : null}
      <FieldInputs
        defs={form.fields as unknown as FieldDef[]}
        values={values}
        onChange={setValues}
        errors={invalid}
      />
      {submit.isError ? (
        <p role="alert" className="services-admin__ko">
          {submit.error instanceof ApiError && submit.error.code === "feedback.already_answered"
            ? t("support:feedback.already")
            : invalid.length
              ? t("support:feedback.fix")
              : t("support:feedback.failed")}
        </p>
      ) : null}
      <div className="feedback-answer__actions">
        <Button variant="ghost" onClick={onDone}>
          {t("support:feedback.cancel")}
        </Button>
        <Button type="submit" disabled={submit.isPending}>
          <Icon name="check" size={16} />
          {t("support:feedback.send")}
        </Button>
      </div>
    </form>
  );
}

type Filter = "all" | "waiting" | "answered";
const FILTERS: Filter[] = ["all", "waiting", "answered"];

/** Where a feedback is: sent, read by the team (or taken up, or set aside), answered. */
/** What the team gave for a feedback (« 100 Xenocoins », « 50 XP », a product), as small badges. */
export function RewardBadges({ rewards }: { rewards: string[] }) {
  const t = useT();
  if (!rewards.length) return null;
  return (
    <ul className="reward-badges" aria-label={t("support:reward.received")}>
      {rewards.map((label, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: the same reward may be given twice
        <li key={index} className="reward-badge">
          <Icon name="gift" size={13} />
          {label}
        </li>
      ))}
    </ul>
  );
}

function Steps({ item }: { item: Mine }) {
  const t = useT();
  const read = item.status !== "new";
  const outcome =
    item.status === "converted" || item.status === "dismissed" ? item.status : read ? "reviewed" : null;
  const steps = [
    { key: "sent", done: true, label: t("support:feedback.step.sent") },
    {
      key: "read",
      done: read,
      label: outcome ? t(`support:feedback.status.${outcome}`) : t("support:feedback.step.read"),
    },
    { key: "answered", done: Boolean(item.reply), label: t("support:feedback.step.answered") },
  ];
  return (
    <ol className="feedback-steps" aria-label={t("support:feedback.step.label")} data-outcome={outcome}>
      {steps.map((step) => (
        <li key={step.key} data-done={step.done || undefined} data-step={step.key}>
          <span className="feedback-steps__dot" aria-hidden="true">
            {step.done ? <Icon name="check" size={10} /> : null}
          </span>
          {step.label}
        </li>
      ))}
    </ol>
  );
}

/**
 * My feedback (027): what I sent, said in my own words first — the kind's icon and colour, when, where it
 * is (sent → read → answered) and the team's reply as a message under mine; a filter keeps the ones still
 * waiting or the answered ones.
 */
function MyFeedback({
  items,
  labels,
  headingId,
}: {
  items: Mine[] | undefined;
  labels: Map<string, string>;
  headingId: string;
}) {
  const t = useT();
  const format = useFormat();
  const [filter, setFilter] = useState<Filter>("all");
  const all = items ?? [];
  const count: Record<Filter, number> = {
    all: all.length,
    waiting: all.filter((i) => !i.reply).length,
    answered: all.filter((i) => i.reply).length,
  };
  const shown = all.filter((i) => (filter === "all" ? true : filter === "answered" ? i.reply : !i.reply));
  const ago = (at: string) => format.relative((Date.parse(at) - Date.now()) / 1000);
  return (
    <section className="feedback-block" aria-labelledby={headingId}>
      <div className="feedback-block__head">
        <h3 id={headingId}>
          <Icon name="inbox" size={18} /> {t("support:feedback.mine")}
        </h3>
        {all.length ? (
          <fieldset className="feedback-filter" aria-label={t("support:feedback.filter.label")}>
            {FILTERS.map((key) => (
              <button
                key={key}
                type="button"
                aria-pressed={filter === key}
                onClick={() => setFilter(key)}
                disabled={key !== "all" && !count[key]}
              >
                {t(`support:feedback.filter.${key}`)}
                <span className="feedback-filter__count">{count[key]}</span>
              </button>
            ))}
          </fieldset>
        ) : null}
      </div>
      {items && !items.length ? <p className="admin-muted">{t("support:feedback.mineEmpty")}</p> : null}
      <ul className="feedback-mine">
        {shown.map((item) => {
          const first = Object.values(item.payload).find((v) => typeof v === "string" && v.trim()) as
            | string
            | undefined;
          const label = item.form_label ?? labels.get(item.form_key) ?? item.form_key;
          return (
            <li key={item.id} className="feedback-mine__item" data-kind={item.kind}>
              <div className="feedback-mine__mine">
                <span className="feedback-mine__icon" aria-hidden="true">
                  <Icon name={KIND_ICONS[item.kind] ?? "message"} size={18} />
                </span>
                <div className="feedback-mine__body">
                  <p className="feedback-mine__meta">
                    <span>{label}</span>
                    <span aria-hidden="true">·</span>
                    <time dateTime={item.created_at} title={format.dateTime(item.created_at)}>
                      {ago(item.created_at)}
                    </time>
                  </p>
                  <p className="feedback-mine__text">{first ?? label}</p>
                  <Steps item={item} />
                  <RewardBadges rewards={item.rewards ?? []} />
                </div>
              </div>
              {item.reply ? (
                <div className="feedback-reply">
                  <p className="feedback-reply__who">
                    <Icon name="message" size={14} /> {t("support:feedback.teamReply")}
                    {item.replied_at ? (
                      <time dateTime={item.replied_at} title={format.dateTime(item.replied_at)}>
                        {ago(item.replied_at)}
                      </time>
                    ) : null}
                  </p>
                  <p className="feedback-reply__text">{item.reply}</p>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/**
 * Feedback (spec 016 T030; 027 redesign): first what the team **asks** (requests open now, answered once),
 * then **giving an opinion** — a few kinds to pick, then a short form (the opinion, a topic, a rating) —
 * and **my feedback**: what I sent, its status and the team's reply.
 */
export function FeedbackPage() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const forms = useForms();
  const requests = useRequests();
  const mine = useMine();
  const [open, setOpen] = useState<string | null>(null);
  const [thanks, setThanks] = useState(false);
  const pending = (requests.data ?? []).filter((r) => !r.answered);
  const done = () => {
    setThanks(true);
    setOpen(null);
  };
  const labels = new Map(
    [...(forms.data ?? []), ...(requests.data ?? []).map((r) => r.form)].map((f) => [f.key, f.label]),
  );
  return (
    <section aria-labelledby={headingId} className="feedback-page">
      <PageHeader
        titleId={headingId}
        level={2}
        icon="message"
        title={t("support:feedback.title")}
        context={t("support:feedback.pitch")}
      />
      {thanks ? (
        <p role="status" className="feedback-thanks">
          <Icon name="heart" size={16} /> {t("support:feedback.thanks")}
        </p>
      ) : null}

      {pending.length ? (
        <section className="feedback-block" aria-labelledby={`${headingId}-asked`}>
          <h3 id={`${headingId}-asked`}>
            <Icon name="megaphone" size={18} /> {t("support:feedback.asked", { count: pending.length })}
          </h3>
          <ul className="feedback-requests">
            {pending.map(({ form }) => (
              <li key={form.key} className="feedback-request" data-open={open === form.key || undefined}>
                <div className="feedback-request__head">
                  <span className="feedback-kind__icon" aria-hidden="true">
                    <Icon name={form.icon ?? "star"} size={22} />
                  </span>
                  <div>
                    <strong>{form.label}</strong>
                    <span className="admin-muted">
                      {t("support:forms.questionCount", { count: form.fields.length })}
                      {form.closes_at
                        ? ` · ${t("support:forms.until", { date: format.date(form.closes_at, "medium") })}`
                        : ""}
                    </span>
                  </div>
                  {open !== form.key ? (
                    <Button onClick={() => setOpen(form.key)}>{t("support:feedback.answer")}</Button>
                  ) : null}
                </div>
                {open === form.key ? <Answer form={form} onDone={done} /> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="feedback-block" aria-labelledby={`${headingId}-give`}>
        <h3 id={`${headingId}-give`}>
          <Icon name="message" size={18} /> {t("support:feedback.give")}
        </h3>
        <ul className="feedback-kinds">
          {(forms.data ?? []).map((form) => (
            <li key={form.key}>
              <button
                type="button"
                className="feedback-kind"
                aria-pressed={open === form.key}
                onClick={() => setOpen(open === form.key ? null : form.key)}
              >
                <span className="feedback-kind__icon" aria-hidden="true">
                  <Icon name={form.icon ?? KIND_ICONS[form.kind] ?? "message"} size={22} />
                </span>
                <span className="feedback-kind__text">
                  <strong>{form.label}</strong>
                  <span className="admin-muted">
                    {form.description || t(`support:feedback.kindHint.${form.kind}`)}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
        {(forms.data ?? [])
          .filter((form) => form.key === open)
          .map((form) => (
            <div key={form.key} className="feedback-request" data-open>
              <Answer form={form} onDone={done} />
            </div>
          ))}
      </section>

      <MyFeedback items={mine.data} labels={labels} headingId={`${headingId}-mine`} />
    </section>
  );
}

export default FeedbackPage;
