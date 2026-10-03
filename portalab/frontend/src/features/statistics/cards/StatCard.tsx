import { useId } from "react";
import { Button } from "../../../design-system/components/Button";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { type CatalogEntry, type StatQuery, useStatistic } from "../api";
import { StatChart } from "../charts/StatChart";

/**
 * One statistic (spec 017 T016): its own query and functional state — locked (hint only), insufficient
 * data, stale/partial with ``as_of``, unavailable — rendered through ``FunctionalState``. Hiding is offered
 * only for hideable statistics.
 */
export function StatCard({
  entry,
  query,
  onHide,
}: {
  entry: CatalogEntry;
  query: Omit<StatQuery, "key">;
  onHide?: () => void;
}) {
  const t = useT();
  const headingId = useId();
  const title = t(entry.title_key);
  const stat = useStatistic({ ...query, key: entry.key }, !entry.locked);
  const result = stat.data;
  return (
    <section aria-labelledby={headingId} className="stat-card" data-statistic={entry.key}>
      <header className="stat-card__header">
        <h3 id={headingId}>{title}</h3>
        {entry.hideable && onHide ? (
          <Button variant="secondary" onClick={onHide}>
            {t("statistics:hide")}
          </Button>
        ) : null}
      </header>
      {entry.locked ? (
        <FunctionalState
          state="unauthorized"
          label={t("statistics:locked")}
          detail={entry.unlock_hint ? t(entry.unlock_hint) : undefined}
        />
      ) : stat.isPending ? (
        <FunctionalState state="loading" />
      ) : stat.isError || !result ? (
        <FunctionalState state="error" onRetry={() => stat.refetch()} />
      ) : result.state === "locked" ? (
        <FunctionalState
          state="unauthorized"
          label={t("statistics:locked")}
          detail={result.unlock_hint ? t(result.unlock_hint) : undefined}
        />
      ) : result.state === "insufficient_data" ? (
        <FunctionalState state="no-data" label={t("statistics:insufficient")} />
      ) : result.state === "unavailable" ? (
        <FunctionalState state="unavailable" onRetry={() => stat.refetch()} />
      ) : result.state === "no_data" ? (
        <FunctionalState state="no-data" />
      ) : (
        <>
          {result.state === "partial" || result.state === "stale" ? (
            <FunctionalState state={result.state} asOf={result.as_of ? new Date(result.as_of) : undefined} />
          ) : null}
          <StatChart result={result} viz={entry.viz} title={title} />
        </>
      )}
    </section>
  );
}
