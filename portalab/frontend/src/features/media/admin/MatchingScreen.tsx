import { useId, useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { MediaError, useAdminActions, useCandidates } from "../api";
import "../media.css";

/**
 * Media identity (spec 024 T015): possible duplicates proposed on fuzzy evidence — never merged without an
 * administrator. Merging asks for an explicit confirmation (server-issued token) and stays reversible.
 */
export function MatchingScreen() {
  const t = useT();
  const headingId = useId();
  const candidates = useCandidates();
  const { merge, reject } = useAdminActions();
  const [pending, setPending] = useState<{ survivor: string; other: string; token: string } | null>(null);
  const [done, setDone] = useState(false);
  const start = (survivor: string, other: string) => {
    setDone(false);
    merge.mutate(
      { survivor, other },
      {
        onError: (error) => {
          const token =
            error instanceof MediaError ? (error.extensions.confirmation as string | undefined) : undefined;
          if (token) setPending({ survivor, other, token });
        },
      },
    );
  };
  const confirm = () => {
    if (!pending) return;
    merge.mutate(
      { survivor: pending.survivor, other: pending.other, confirmation: pending.token },
      {
        onSuccess: () => {
          setPending(null);
          setDone(true);
        },
      },
    );
  };
  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId}>{t("media:admin.title")}</h2>
      <h3>{t("media:admin.candidates")}</h3>
      {pending ? (
        <div role="alertdialog" aria-labelledby={`${headingId}-confirm`}>
          <p id={`${headingId}-confirm`}>{t("media:admin.confirm")}</p>
          <Button onClick={confirm}>{t("media:admin.merge")}</Button>{" "}
          <Button variant="secondary" onClick={() => setPending(null)}>
            {t("media:requests.cancel")}
          </Button>
        </div>
      ) : null}
      <p aria-live="polite">{done ? t("media:admin.merged") : ""}</p>
      {candidates.isPending ? <FunctionalState state="loading" /> : null}
      {candidates.isError ? (
        <FunctionalState state="unavailable" onRetry={() => candidates.refetch()} />
      ) : null}
      {candidates.data && candidates.data.length === 0 ? <p>{t("media:admin.empty")}</p> : null}
      <ul className="media-list">
        {(candidates.data ?? []).map((c) => (
          <li key={c.id}>
            <Link to={`/media/${c.object_a.id}`}>{c.object_a.title}</Link> ↔{" "}
            <Link to={`/media/${c.object_b.id}`}>{c.object_b.title}</Link> ·{" "}
            {t("media:admin.score", { score: c.score.toFixed(2) })}{" "}
            <Button variant="secondary" onClick={() => start(c.object_a.id, c.object_b.id)}>
              {t("media:admin.merge")}
            </Button>{" "}
            <Button variant="secondary" onClick={() => reject.mutate(c.id)}>
              {t("media:admin.reject")}
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default MatchingScreen;
