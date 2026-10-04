import { useId, useState } from "react";
import "../support.css";
import { Button } from "../../../design-system/components/Button";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { useFeedbackActions, useFeedbackDetail, useFeedbackQueue } from "../tickets/api";

/**
 * Feedback review (spec 016 T030/T032, staff): read, dismiss, or convert explicitly — a target whose owner
 * is unavailable is shown disabled with its reason; sensitive conversions ask for a confirmation.
 */
function Detail({ id }: { id: string }) {
  const t = useT();
  const detail = useFeedbackDetail(id);
  const { convert, review } = useFeedbackActions(id);
  const [pending, setPending] = useState<{ target: string; token: string } | null>(null);
  if (!detail.data) return <FunctionalState state="loading" />;
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
  return (
    <div className="support-feedback-detail">
      <dl>
        {Object.entries(detail.data.payload).map(([key, value]) => (
          <div key={key}>
            <dt>{key}</dt>
            <dd>{String(value)}</dd>
          </div>
        ))}
      </dl>
      <div className="ds-stack ds-stack--row">
        {detail.data.conversions.map((c) => (
          <Button
            key={c.target}
            variant="secondary"
            disabled={!c.available || Boolean(c.done)}
            title={c.reason ? t(`support:convert.reason.${c.reason}`) : undefined}
            onClick={() => start(c.target)}
          >
            {t(`support:convert.${c.target}`)}
            {c.done ? ` ✓` : ""}
            {c.reason ? (
              <span className="visually-hidden"> ({t(`support:convert.reason.${c.reason}`)})</span>
            ) : null}
          </Button>
        ))}
        <Button variant="secondary" onClick={() => review.mutate("dismiss")}>
          {t("support:feedback.dismiss")}
        </Button>
      </div>
      {pending ? (
        <div role="alertdialog" aria-label={t("support:convert.confirm")}>
          <p>{t("support:convert.confirm")}</p>
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
      ) : null}
    </div>
  );
}

export function ReviewQueue() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const queue = useFeedbackQueue();
  const [open, setOpen] = useState<string | null>(null);
  return (
    <section aria-labelledby={headingId}>
      <PageHeader titleId={headingId} level={2} icon="message" title={t("support:review.title")} />
      {queue.isError ? <FunctionalState state="unauthorized" /> : null}
      {queue.data && queue.data.length === 0 ? <p>{t("support:review.empty")}</p> : null}
      <ul className="support-list">
        {(queue.data ?? []).map((item) => (
          <li key={item.id}>
            <Button
              variant="secondary"
              aria-expanded={open === item.id}
              onClick={() => setOpen(open === item.id ? null : item.id)}
            >
              {item.kind} · {item.status} · {format.dateTime(item.created_at)}
            </Button>
            {open === item.id ? <Detail id={item.id} /> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default ReviewQueue;
