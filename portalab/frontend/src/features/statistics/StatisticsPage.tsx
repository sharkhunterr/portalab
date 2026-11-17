import { AdminGrid, AdminPage, AdminSection } from "../../design-system/admin/AdminKit";
import { SelectField } from "../../design-system/components/Field";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { Switch } from "../account/SettingsKit";
import { type PeriodKind, useCatalog, useHiddenSections } from "./api";
import { StatCard, StatTile } from "./cards/StatCard";
import "../admin/admin.css";
import { useState } from "react";

/**
 * Statistics (spec 017 T016; US1): the administrator-defined statistics the user may see — choose a period,
 * hide/show hideable sections. Users never author charts or queries here (no builder exists). Issue 481:
 * My media's look — the page head with its period, the single figures as tiles, the charts as sections.
 */
const PERIODS: Array<{ value: string; kind: PeriodKind; days?: number }> = [
  { value: "7", kind: "last_n_days", days: 7 },
  { value: "30", kind: "last_n_days", days: 30 },
  { value: "week", kind: "week" },
  { value: "month", kind: "month" },
  { value: "year", kind: "year" },
];

/** issue 298: the community's and the portal's figures (``/statistics``), or mine (``/statistics/me``). */
export function StatisticsPage({ mine = false }: { mine?: boolean }) {
  const t = useT();
  const catalog = useCatalog();
  const { hidden, save } = useHiddenSections();
  const [period, setPeriod] = useState("30");
  const choice = PERIODS.find((p) => p.value === period) ?? PERIODS[1];
  const query = { period: choice?.kind ?? "last_n_days", ...(choice?.days ? { days: choice.days } : {}) };
  const entries = (catalog.data ?? []).filter((e) => (e.scope === "personal") === mine);
  const visible = entries.filter((e) => !hidden.includes(e.key));
  // issue 298: the single figures first, as tiles, then the charts
  const figures = visible.filter((e) => e.viz === "number");
  const charts = visible.filter((e) => e.viz !== "number");
  const hide = (key: string) => () => save.mutate([...hidden, key]);
  const hideable = entries.filter((e) => e.hideable);
  return (
    <AdminPage
      icon="chart"
      title={t(mine ? "statistics:mineTitle" : "statistics:title")}
      description={t(mine ? "statistics:mineDescription" : "statistics:description")}
      secondary={
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
      }
    >
      {catalog.isPending ? <FunctionalState state="loading" /> : null}
      {catalog.isError ? <FunctionalState state="error" onRetry={() => catalog.refetch()} /> : null}
      {catalog.data && entries.length === 0 ? (
        <FunctionalState state="no-data" label={t("statistics:empty")} />
      ) : null}
      {figures.length ? (
        <ul className="admin-stats statistics-tiles" aria-label={t("statistics:figures")}>
          {figures.map((entry) => (
            <StatTile key={entry.key} entry={entry} query={query} onHide={hide(entry.key)} />
          ))}
        </ul>
      ) : null}
      {charts.length ? (
        <AdminGrid>
          {charts.map((entry) => (
            <StatCard key={entry.key} entry={entry} query={query} onHide={hide(entry.key)} />
          ))}
        </AdminGrid>
      ) : null}
      {hideable.length ? (
        <AdminSection title={t("statistics:shown")} icon="sliders" description={t("statistics:shownHint")}>
          <div className="statistics-shown">
            {hideable.map((entry) => (
              <Switch
                key={entry.key}
                label={t(entry.title_key)}
                checked={!hidden.includes(entry.key)}
                onChange={(event) =>
                  save.mutate(
                    event.target.checked ? hidden.filter((key) => key !== entry.key) : [...hidden, entry.key],
                  )
                }
              />
            ))}
          </div>
        </AdminSection>
      ) : null}
    </AdminPage>
  );
}

export default StatisticsPage;
