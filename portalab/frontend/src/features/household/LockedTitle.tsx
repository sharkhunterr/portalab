import { useState } from "react";
import { Link } from "react-router";
import { Button } from "../../design-system/components/Button";
import { TextAreaField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import type { ApiError } from "../../state/regions";
import { useAccessRequests, useAskAccess } from "./api";
import "./household.css";

/** The problem code of a title a household profile's age rating keeps from it (spec 032). */
export const RESTRICTED = "household.restricted";
const REASONS = ["age", "unrated", "genre", "keyword", "type", "title", "warning"];

/** Issue 478: the warnings a title is kept for (reason « warning »), named. */
function Warnings({ warnings }: { warnings: unknown }) {
  const t = useT();
  const list = Array.isArray(warnings) ? warnings.map(String) : [];
  if (!list.length) return null;
  return (
    <ul className="household-locked__warnings" aria-label={t("household:locked.warnings")}>
      {list.map((kind) => (
        <li key={kind} className="household-badge">
          <Icon name="warning" size={14} />
          {t(`household:warning.${kind}`)}
        </li>
      ))}
    </ul>
  );
}

/** A title above the profile's age rating: what it is, and « Ask for access » to the account's master. */
export function LockedTitle({ problem }: { problem: ApiError }) {
  const t = useT();
  const ref = String(problem.extensions.object_id ?? "");
  const title = String(problem.extensions.name ?? "") || "…";
  const rating = problem.extensions.rating ? String(problem.extensions.rating) : null;
  const reason = String(problem.extensions.reason ?? "age");
  return (
    <section className="household-locked" aria-labelledby="household-locked">
      <span className="household-locked__icon" aria-hidden="true">
        <Icon name="lock" size={32} />
      </span>
      <h1 id="household-locked">{t("household:locked.title")}</h1>
      {rating ? <span className="household-badge">{t("household:locked.rating", { rating })}</span> : null}
      <p>{t(`household:locked.why.${REASONS.includes(reason) ? reason : "age"}`, { title })}</p>
      {reason === "warning" ? <Warnings warnings={problem.extensions.warnings} /> : null}
      <AskAccess objectId={ref} title={title} rating={rating} canAsk={problem.extensions.can_ask !== false} />
      <Link to="/media" className="ds-link">
        {t("household:locked.back")}
      </Link>
    </section>
  );
}

/** Issue 432: a title shown to the profile (its page opens) but kept from it — why, and « Ask for access ». */
export function KeptNotice({
  objectId,
  title,
  kept,
}: {
  objectId: string;
  title: string;
  kept: { rating?: string | null; reason?: string | null; can_ask?: boolean; warnings?: string[] };
}) {
  const t = useT();
  const reason = kept.reason && REASONS.includes(kept.reason) ? kept.reason : "age";
  return (
    <section className="household-kept-notice" aria-labelledby={`kept-${objectId}`}>
      <span className="household-locked__icon" aria-hidden="true">
        <Icon name="lock" size={22} />
      </span>
      <div>
        <h2 id={`kept-${objectId}`}>{t("household:kept.title", { title })}</h2>
        {kept.rating ? (
          <span className="household-badge">{t("household:locked.rating", { rating: kept.rating })}</span>
        ) : null}
        <p>{t(`household:locked.why.${reason}`, { title })}</p>
        {reason === "warning" ? <Warnings warnings={kept.warnings} /> : null}
        <AskAccess
          objectId={objectId}
          title={title}
          rating={kept.rating ?? null}
          canAsk={kept.can_ask !== false}
        />
      </div>
    </section>
  );
}

/** « Ask for access »: the profile's latest request for this title (waiting, refused), or the form. */
function AskAccess({
  objectId,
  title,
  rating,
  canAsk,
}: {
  objectId: string;
  title: string;
  rating: string | null;
  canAsk: boolean;
}) {
  const t = useT();
  const format = useFormat();
  const ask = useAskAccess();
  const [note, setNote] = useState("");
  const last = (useAccessRequests().data ?? []).find((r) => r.kind === "media" && r.subject_ref === objectId);
  const pending = last?.status === "pending";
  if (!canAsk) return <p>{t("household:locked.noAsk")}</p>;
  if (ask.isSuccess || pending)
    return (
      <p role="status" className="household-locked__pending">
        <Icon name="hourglass" size={16} />
        {last?.created_at && !ask.isSuccess
          ? t("household:locked.pendingSince", { date: format.dateTime(last.created_at) })
          : t("household:locked.asked")}
      </p>
    );
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        ask.mutate({ ref: objectId, title, rating, ...(note.trim() ? { note: note.trim() } : {}) });
      }}
    >
      <TextAreaField
        label={t("household:locked.note")}
        value={note}
        maxLength={300}
        rows={2}
        onChange={(event) => setNote(event.target.value)}
      />
      {last?.status === "denied" && last.decided_at ? (
        <p className="household-locked__denied">
          {t("household:locked.denied", { date: format.dateTime(last.decided_at) })}
        </p>
      ) : null}
      <Button type="submit" disabled={ask.isPending || !objectId}>
        <Icon name="key" size={16} />
        {t("household:locked.ask")}
      </Button>
      {ask.isError ? <p role="alert">{t("household:error")}</p> : null}
    </form>
  );
}
