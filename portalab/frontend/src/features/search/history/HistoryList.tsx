import { useId } from "react";
import { Button } from "../../../design-system/components/Button";
import { useT } from "../../../i18n/hooks/useT";
import { useHistory, useHistoryActions } from "../api";

/** Recent searches (spec 008 T026; FR-019..021): private to the user, re-runnable, removable, clearable. */
export function HistoryList({ onPick }: { onPick: (query: string) => void }) {
  const t = useT();
  const headingId = useId();
  const history = useHistory();
  const { remove, clear } = useHistoryActions();
  const entries = history.data ?? [];
  return (
    <section aria-labelledby={headingId} className="search-history">
      <h3 id={headingId}>{t("search:history.title")}</h3>
      {entries.length === 0 ? (
        <p>{t("search:history.empty")}</p>
      ) : (
        <>
          <ul>
            {entries.map((entry) => (
              <li key={entry.id} className="ds-stack ds-stack--row">
                <Button variant="secondary" onClick={() => onPick(entry.query)}>
                  {entry.query}
                </Button>
                <Button
                  variant="secondary"
                  aria-label={t("search:history.remove", { query: entry.query })}
                  onClick={() => remove.mutate(entry.id)}
                >
                  ×
                </Button>
              </li>
            ))}
          </ul>
          <Button variant="secondary" onClick={() => clear.mutate()}>
            {t("search:history.clear")}
          </Button>
        </>
      )}
    </section>
  );
}
