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
import { Menu } from "../../../design-system/components/Overlays";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import type { FieldDef } from "../tickets/api";
import { useFeedbackActions, useFeedbackDetail } from "../tickets/api";
import { optionLabel } from "../tickets/FieldInputs";
import { FeedbackReward, useCanReward } from "./FeedbackReward";
import "../support.css";

type Item = components["schemas"]["FeedbackOut"];
type Results = components["schemas"]["FeedbackResultsOut"];
type FormRow = {
  key: string;
  label: string;
  fields: FieldDef[];
  requested?: boolean;
  closes_at?: string | null;
};

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

const STEP_OF: Record<string, number> = { new: 0, reviewed: 1, converted: 2, dismissed: 1 };
const MORE_ICON: Record<string, string> = {
  contribution: "award",
  feature_proposal: "lightbulb",
  community_project: "users",
};

/** Where the feedback stands, as the member sees it: sent, read, answered (or taken up). */
function Flow({ item }: { item: Item }) {
  const t = useT();
  const reached = item.reply ? 2 : (STEP_OF[item.status] ?? 0);
  const steps = ["sent", "read", "answered"] as const;
  return (
    <ol className="feedback-flow" aria-label={t("support:feedback.step.label")}>
      {steps.map((step, index) => (
        <li
          key={step}
          data-done={index <= reached || undefined}
          data-current={index === reached || undefined}
        >
          <span className="feedback-flow__dot" aria-hidden="true">
            {index < reached ? <Icon name="check" size={12} /> : null}
          </span>
          {t(`support:feedback.step.${step}`)}
        </li>
      ))}
    </ol>
  );
}

/**
 * One feedback, handled like a ticket (027): where it stands, the conversation (the member's answers, the
 * team's reply), a toolbar of big actions — reward, make a ticket, mark read or set aside, and « more » for
 * the other conversions — and a composer to answer, thumb-friendly on a phone.
 */
function Detail({ item, fields }: { item: Item; fields: FieldDef[] }) {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const detail = useFeedbackDetail(item.id);
  const { convert, review } = useFeedbackActions(item.id);
  const canReward = useCanReward(item);
  const [reply, setReply] = useState("");
  const [pending, setPending] = useState<{ target: string; token: string } | null>(null);
  const [rewarded, setRewarded] = useState(false);
  const send = useMutation({
    mutationFn: async () =>
      (
        await api.POST("/api/v1/support/feedback/{feedback_id}/reply", {
          params: { path: { feedback_id: item.id } },
          // the earlier reply stays: the new one follows it (the member keeps the whole exchange)
          body: { text: item.reply ? `${item.reply}\n\n${reply.trim()}` : reply.trim() },
        })
      ).data,
    onSuccess: () => {
      setReply("");
      void client.invalidateQueries({ queryKey: [...QUEUE] });
    },
  });
  const start = (target: string) =>
    convert.mutate(
      { target },
      {
        onError: (error) => {
          const token =
            error instanceof ApiError ? (error.extensions.confirmation as string | undefined) : undefined;
          if (token) setPending({ target, token });
        },
      },
    );
  const conversions = detail.data?.conversions ?? [];
  const ticket = conversions.find((c) => c.target === "ticket");
  const others = conversions.filter((c) => c.target !== "ticket");
  const open = item.status !== "dismissed" && item.status !== "converted";
  const name = item.submitter_name ?? t("support:review.someone");
  const more = [
    ...others.map((c) => ({
      key: c.target,
      icon: MORE_ICON[c.target] ?? "sparkles",
      label: `${t(`support:convert.${c.target}`)}${c.done ? " ✓" : ""}${
        c.reason ? ` (${t(`support:convert.reason.${c.reason}`)})` : ""
      }`,
      disabled: !c.available || Boolean(c.done),
      onSelect: () => start(c.target),
    })),
    ...(open && item.status === "new"
      ? [
          {
            key: "dismiss",
            icon: "close",
            label: t("support:feedback.dismiss"),
            separated: others.length > 0,
            onSelect: () => review.mutate("dismiss"),
          },
        ]
      : []),
  ];
  return (
    <div className="feedback-detail">
      <Flow item={item} />
      <ol className="feedback-thread" aria-label={t("support:review.conversation")}>
        <li className="feedback-bubble" data-from="member">
          <span className="feedback-bubble__who">
            {name} · {format.relative((Date.parse(item.created_at) - Date.now()) / 1000)}
          </span>
          <Answers payload={item.payload} fields={fields} />
        </li>
        {item.reply ? (
          <li className="feedback-bubble" data-from="team">
            <span className="feedback-bubble__who">
              {t("support:review.team")}
              {item.replied_at
                ? ` · ${format.relative((Date.parse(item.replied_at) - Date.now()) / 1000)}`
                : ""}
            </span>
            <p>{item.reply}</p>
          </li>
        ) : null}
      </ol>
      <div className="feedback-tools" role="toolbar" aria-label={t("support:review.tools")}>
        {canReward ? (
          <FeedbackReward
            item={item}
            onDone={() => setRewarded(true)}
            trigger={
              <button type="button" className="feedback-tool" data-tone="reward">
                <Icon name="gift" size={22} />
                <span>{t("support:review.tool.reward")}</span>
              </button>
            }
          />
        ) : null}
        {ticket ? (
          <button
            type="button"
            className="feedback-tool"
            disabled={!ticket.available || Boolean(ticket.done)}
            title={ticket.reason ? t(`support:convert.reason.${ticket.reason}`) : undefined}
            onClick={() => start("ticket")}
          >
            <Icon name={ticket.done ? "check" : "ticket"} size={22} />
            <span>{t(ticket.done ? "support:review.tool.ticketDone" : "support:review.tool.ticket")}</span>
          </button>
        ) : null}
        {item.status === "new" ? (
          <button type="button" className="feedback-tool" onClick={() => review.mutate("review")}>
            <Icon name="check" size={22} />
            <span>{t("support:review.tool.read")}</span>
          </button>
        ) : open ? (
          <button type="button" className="feedback-tool" onClick={() => review.mutate("dismiss")}>
            <Icon name="close" size={22} />
            <span>{t("support:feedback.dismiss")}</span>
          </button>
        ) : null}
        {more.length ? (
          <Menu
            label={t("support:review.tool.more")}
            align="end"
            items={more}
            trigger={
              <button type="button" className="feedback-tool">
                <Icon name="more" size={22} />
                <span>{t("support:review.tool.more")}</span>
              </button>
            }
          />
        ) : null}
      </div>
      {rewarded ? <p role="status">{t("support:reward.done")}</p> : null}
      {send.isSuccess ? <p role="status">{t("support:review.replied")}</p> : null}
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
      <form
        className="feedback-composer"
        onSubmit={(event) => {
          event.preventDefault();
          if (reply.trim() && !send.isPending) send.mutate();
        }}
      >
        <label htmlFor={`reply-${item.id}`} className="visually-hidden">
          {t("support:review.replyTo", { name })}
        </label>
        <textarea
          id={`reply-${item.id}`}
          rows={2}
          value={reply}
          placeholder={item.reply ? t("support:review.replyAgain") : t("support:review.replyTo", { name })}
          onChange={(e) => setReply(e.target.value)}
        />
        <button
          type="submit"
          className="feedback-composer__send"
          disabled={!reply.trim() || send.isPending}
          aria-label={t("support:review.sendReply")}
        >
          <Icon name="send" size={20} />
        </button>
      </form>
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
      <p className="feedback-results__total">
        {t("support:review.answers", { count: results.data.total })}
        {form.closes_at
          ? ` · ${t("support:forms.until", { date: format.date(form.closes_at, "medium") })}`
          : ""}
      </p>
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
            { key: "requests", label: t("support:review.tabs.requests"), count: requested.length },
          ]}
        />
      }
    >
      {queue.isError ? <FunctionalState state="unauthorized" /> : null}
      {status === "requests" ? (
        requested.length ? (
          requested.map((form) => (
            <AdminSection key={form.key} span="full" icon="star" title={form.label}>
              <ResultsPanel form={form} />
            </AdminSection>
          ))
        ) : (
          <AdminEmpty icon="star" title={t("support:review.noRequests")} />
        )
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
