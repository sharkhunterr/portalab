import { useId, useState } from "react";
import { BarsChart, LinesChart } from "../../../design-system/charts/Charts";
import { Button } from "../../../design-system/components/Button";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { StatResult } from "../api";

/**
 * Accessible chart (spec 017 T016; R12): an SVG chart (Recharts, theme tokens) **plus** a text summary and
 * a data table alternative — the meaning never depends on color alone; patterns via stroke dashes.
 */
export function StatChart({ result, viz, title }: { result: StatResult; viz: string; title: string }) {
  const t = useT();
  const format = useFormat();
  const tableId = useId();
  const [table, setTable] = useState(false);
  const series = result.series.map((point) => ({ day: String(point.day), value: Number(point.value ?? 0) }));
  const summary =
    result.value === null
      ? t("statistics:summary.none")
      : t("statistics:summary.value", { title, value: format.number(result.value) });
  return (
    <figure className="stat-chart">
      <figcaption>
        <p className="stat-chart__summary">{summary}</p>
        {result.trend ? (
          <p className="stat-chart__trend" data-direction={result.trend.direction}>
            {t(`statistics:trend.${result.trend.direction}`, {
              delta: format.number(result.trend.delta),
              percent: result.trend.percent === null ? "—" : format.percent(result.trend.percent / 100),
            })}
          </p>
        ) : null}
      </figcaption>
      {viz !== "number" && series.length ? (
        <div className="stat-chart__plot" aria-hidden="true">
          {viz === "bar" ? (
            <BarsChart
              data={series}
              x="day"
              height={220}
              legend={false}
              format={(value) => format.number(value)}
              series={[{ key: "value", label: title, color: "var(--color-accent)" }]}
            />
          ) : (
            <LinesChart
              data={series}
              x="day"
              area
              height={220}
              legend={false}
              format={(value) => format.number(value)}
              series={[{ key: "value", label: title, color: "var(--color-accent)" }]}
            />
          )}
        </div>
      ) : null}
      <Button
        variant="secondary"
        aria-expanded={table}
        aria-controls={tableId}
        onClick={() => setTable((v) => !v)}
      >
        {table ? t("statistics:table.hide") : t("statistics:table.show")}
      </Button>
      <div id={tableId} hidden={!table}>
        <table className="stat-chart__table">
          <caption>{title}</caption>
          <thead>
            <tr>
              <th scope="col">{t("statistics:table.day")}</th>
              <th scope="col">{t("statistics:table.value")}</th>
            </tr>
          </thead>
          <tbody>
            {series.map((point) => (
              <tr key={point.day}>
                <th scope="row">{format.date(point.day)}</th>
                <td>{format.number(point.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {result.breakdown.length ? (
          <table className="stat-chart__table">
            <caption>{t("statistics:table.breakdown")}</caption>
            <tbody>
              {result.breakdown.map((cell) => {
                const label = Object.values(cell.dims as Record<string, string>).join(" · ");
                return (
                  <tr key={label}>
                    <th scope="row">{label === "other" ? t("statistics:table.other") : label}</th>
                    <td>{format.number(Number(cell.value ?? 0))}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : null}
      </div>
    </figure>
  );
}
