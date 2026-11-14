import { useState } from "react";
import { Link } from "react-router";
import { Button } from "../../design-system/components/Button";
import { TextAreaField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import type { ApiError } from "../../state/regions";
import { useAskAccess } from "./api";
import "./household.css";

/** The problem code of a title a household profile's age rating keeps from it (spec 032). */
export const RESTRICTED = "household.restricted";

/** A title above the profile's age rating: what it is, and « Ask for access » to the account's master. */
export function LockedTitle({ problem }: { problem: ApiError }) {
  const t = useT();
  const ask = useAskAccess();
  const [note, setNote] = useState("");
  const ref = String(problem.extensions.object_id ?? "");
  const title = String(problem.extensions.name ?? "") || "…";
  const rating = problem.extensions.rating ? String(problem.extensions.rating) : null;
  return (
    <section className="household-locked" aria-labelledby="household-locked">
      <span className="household-locked__icon" aria-hidden="true">
        <Icon name="lock" size={32} />
      </span>
      <h1 id="household-locked">{t("household:locked.title")}</h1>
      {rating ? <span className="household-badge">{t("household:locked.rating", { rating })}</span> : null}
      <p>{t("household:locked.body", { title })}</p>
      {problem.extensions.can_ask === false ? (
        <p>{t("household:locked.noAsk")}</p>
      ) : ask.isSuccess ? (
        <p role="status">{t("household:locked.asked")}</p>
      ) : (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            ask.mutate({ ref, title, rating, ...(note.trim() ? { note: note.trim() } : {}) });
          }}
        >
          <TextAreaField
            label={t("household:locked.note")}
            value={note}
            maxLength={300}
            rows={2}
            onChange={(event) => setNote(event.target.value)}
          />
          <Button type="submit" disabled={ask.isPending || !ref}>
            <Icon name="key" size={16} />
            {t("household:locked.ask")}
          </Button>
          {ask.isError ? <p role="alert">{t("household:error")}</p> : null}
        </form>
      )}
      <Link to="/media" className="ds-link">
        {t("household:locked.back")}
      </Link>
    </section>
  );
}
