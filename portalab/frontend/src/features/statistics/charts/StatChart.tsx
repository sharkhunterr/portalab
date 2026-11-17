import { useId, useState } from "react";
import { BarsChart, LinesChart } from "../../../design-system/charts/Charts";
import { Button } from "../../../design-system/components/Button";
import { useFormat } from "../../../i18n/format/useFormat";
import { type Translate, useT } from "../../../i18n/hooks/useT";
import { useAchievements } from "../../gamification/api";
import type { StatResult } from "../api";
import { TrendBadge } from "../cards/look";

type Cell = StatResult["breakdown"][number];

/** issue 298: a breakdown's value in words — its translation (a media kind, a state, a reward's source…), an
 * achievement's name, else the value made readable. */
function dimText(t: Translate, names: Map<string, string>, dims: Record<string, string>): string {
  return Object.entries(dims)
    .map(([name, value]) => {
      if (value === "other") return t("statistics:table.other");
      if (name === "achievement" && names.has(value)) return names.get(value) as string;
      const id = `statistics:dim.${name}.${value}`;
      const text = t(id);
      return text === id.split(":")[1] ? value.replaceAll("_", " ") : text;
    })
    .join(" · ");
}

/** issue 298: what the total is made of, in sight (not only in the data table) — the largest first, with its
 * share drawn as a bar and written as a number. */
function Breakdown({ cells, total, names }: { cells: Cell[]; total: number; names: Map<string, string> }) {
  const t = useT();
  const format = useFormat();
  const sorted = [...cells].sort((a, b) => Number(b.value ?? 0) - Number(a.value ?? 0));
  const sum = total || sorted.reduce((acc, cell) => acc + Number(cell.value ?? 0), 0) || 1;
  return (
    <ul className="stat-breakdown" aria-label={t("statistics:table.breakdown")}>
      {sorted.map((cell) => {
        const value = Number(cell.value ?? 0);
        const share = Math.round((value / sum) * 100);
        const label = dimText(t, names, cell.dims as Record<string, string>);
        return (
          <li key={label}>
            <span className="stat-breakdown__label">{label}</span>
            <span className="stat-breakdown__bar" aria-hidden="true">
              <span style={{ inlineSize: `${share}%` }} />
            </span>
            <span className="stat-breakdown__value">
              {format.number(value)} <small>({share} %)</small>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** issue 482: the previous period, in grey behind the period's colour */
const PREVIOUS = "color-mix(in srgb, var(--color-text-muted) 55%, transparent)";

/**
 * Accessible chart (spec 017 T016; R12): an SVG chart (Recharts, theme tokens) **plus** a text summary and
 * a data table alternative — the meaning never depends on color alone; patterns via stroke dashes.
 */
export function StatChart({ result, viz, title }: { result: StatResult; viz: string; title: string }) {
  const t = useT();
  const format = useFormat();
  const tableId = useId();
  const [table, setTable] = useState(false);
  // issue 482: the period's days, each with the previous period's value on the same rank (drawn in grey);
  // a day without events is 0
  const previous = new Map(
    (result.previous_series ?? []).map((point) => [String(point.day), Number(point.value ?? 0)]),
  );
  const current = new Map(result.series.map((point) => [String(point.day), Number(point.value ?? 0)]));
  const days = previous.size
    ? [...new Set([...previous.keys(), ...current.keys()])].sort()
    : [...current.keys()].sort();
  const series = days.map((key) => ({
    day: key,
    value: current.get(key) ?? 0,
    ...(previous.size ? { previous: previous.get(key) ?? null } : {}),
  }));
  const drawn = [
    ...(previous.size
      ? [{ key: "previous", label: t("statistics:previousPeriod"), color: PREVIOUS, dashed: true }]
      : []),
    { key: "value", label: title, color: "var(--color-accent)" },
  ];
  // issue 298: the days as the language writes them (« 5 oct. »), not as ISO dates
  const day = (value: string) => {
    const leaf = format.dayMonth(value);
    return `${leaf.day} ${leaf.month}`;
  };
  const achievements = useAchievements().data;
  const names = new Map(
    (Array.isArray(achievements) ? achievements : []).map((a) => [a.key, a.label ?? a.key]),
  );
  const summary =
    result.value === null
      ? t("statistics:summary.none")
      : t("statistics:summary.value", { title, value: format.number(result.value) });
  return (
    <figure className="stat-chart">
      <figcaption>
        {/* issue 298: the figure, big — the card's heading already names it */}
        <p className="stat-chart__summary">
          <span aria-hidden="true">{result.value === null ? "—" : format.number(result.value)}</span>
          <span className="visually-hidden">{summary}</span>
          <TrendBadge result={result} />
        </p>
      </figcaption>
      {viz !== "number" && series.length ? (
        <div className="stat-chart__plot" aria-hidden="true">
          {viz === "bar" ? (
            <BarsChart
              data={series}
              x="day"
              xFormat={day}
              height={220}
              legend={drawn.length > 1}
              format={(value) => format.number(value)}
              series={drawn}
            />
          ) : (
            <LinesChart
              data={series}
              x="day"
              xFormat={day}
              area
              height={220}
              legend={drawn.length > 1}
              format={(value) => format.number(value)}
              series={drawn}
            />
          )}
        </div>
      ) : null}
      {result.breakdown.length > 1 ? (
        <Breakdown cells={result.breakdown} total={Number(result.value ?? 0)} names={names} />
      ) : null}
      <Button
        variant="ghost"
        className="stat-chart__toggle"
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
              {previous.size ? <th scope="col">{t("statistics:previousPeriod")}</th> : null}
            </tr>
          </thead>
          <tbody>
            {series.map((point) => (
              <tr key={point.day}>
                <th scope="row">{format.date(point.day)}</th>
                <td>{format.number(point.value)}</td>
                {previous.size ? (
                  <td>
                    {point.previous === null || point.previous === undefined
                      ? "—"
                      : format.number(point.previous)}
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
        {result.breakdown.length ? (
          <table className="stat-chart__table">
            <caption>{t("statistics:table.breakdown")}</caption>
            <tbody>
              {result.breakdown.map((cell) => {
                const label = dimText(t, names, cell.dims as Record<string, string>);
                return (
                  <tr key={label}>
                    <th scope="row">{label}</th>
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
