import { useId, useState } from "react";
import { Button } from "../../design-system/components/Button";
import { SelectField } from "../../design-system/components/Field";
import { PageHeader } from "../../design-system/components/PageHeader";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { type PeriodKind, useCatalog, useHiddenSections } from "./api";
import { StatCard } from "./cards/StatCard";

/**
 * Statistics (spec 017 T016; US1): the administrator-defined statistics the user may see — choose a period,
 * hide/show hideable sections. Users never author charts or queries here (no builder exists).
 */
const PERIODS: Array<{ value: string; kind: PeriodKind; days?: number }> = [
  { value: "7", kind: "last_n_days", days: 7 },
  { value: "30", kind: "last_n_days", days: 30 },
  { value: "week", kind: "week" },
  { value: "month", kind: "month" },
  { value: "year", kind: "year" },
];

export function StatisticsPage() {
  const t = useT();
  const headingId = useId();
  const catalog = useCatalog();
  const { hidden, save } = useHiddenSections();
  const [period, setPeriod] = useState("30");
  const choice = PERIODS.find((p) => p.value === period) ?? PERIODS[1];
  const query = { period: choice?.kind ?? "last_n_days", ...(choice?.days ? { days: choice.days } : {}) };
  const entries = catalog.data ?? [];
  const visible = entries.filter((e) => !hidden.includes(e.key));
  const hiddenEntries = entries.filter((e) => hidden.includes(e.key));
  return (
    <section aria-labelledby={headingId} className="statistics-page">
      <PageHeader titleId={headingId} level={2} icon="chart" title={t("statistics:title")} />
      <SelectField
        label={t("statistics:period")}
        value={period}
        onChange={(event) => setPeriod(event.target.value)}
      >
        {PERIODS.map((p) => (
          <option key={p.value} value={p.value}>
            {t(`statistics:period.${p.value}`)}
          </option>
        ))}
      </SelectField>
      {catalog.isPending ? <FunctionalState state="loading" /> : null}
      {catalog.isError ? <FunctionalState state="error" onRetry={() => catalog.refetch()} /> : null}
      {catalog.data && entries.length === 0 ? (
        <FunctionalState state="no-data" label={t("statistics:empty")} />
      ) : null}
      <div className="statistics-grid">
        {visible.map((entry) => (
          <StatCard
            key={entry.key}
            entry={entry}
            query={query}
            onHide={() => save.mutate([...hidden, entry.key])}
          />
        ))}
      </div>
      {hiddenEntries.length ? (
        <section className="ds-panel" aria-label={t("statistics:hidden")}>
          <h3>{t("statistics:hidden")}</h3>
          <ul>
            {hiddenEntries.map((entry) => (
              <li key={entry.key}>
                {t(entry.title_key)}{" "}
                <Button
                  variant="secondary"
                  onClick={() => save.mutate(hidden.filter((key) => key !== entry.key))}
                >
                  {t("statistics:show")}
                </Button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  );
}

export default StatisticsPage;
