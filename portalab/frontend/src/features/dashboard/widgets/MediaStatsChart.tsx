import { useEffect, useRef, useState } from "react";
import { BarsChart, DonutChart, LinesChart } from "../../../design-system/charts/Charts";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useMeasures } from "../../media/insights/api";

/**
 * Charts of the « media statistics » widget (027), loaded on demand: bars or an area over time, or a donut
 * by kind. A short text summary always comes with them (the chart never carries meaning alone). Issue 117:
 * drawn by the chart kit — the portal's other charts' shapes and look, kept to the widget's room.
 */
export interface StatsPoint {
  date: string;
  seconds: number;
  plays: number;
}

export default function MediaStatsChart({
  chart,
  metric,
  unit,
  timeline,
  byKind,
}: {
  chart: "bars" | "area" | "donut";
  metric: "time" | "plays";
  unit: string;
  timeline: StatsPoint[];
  byKind: Array<{ kind: string; seconds: number; plays: number }>;
}) {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  // issue 117: the chart follows its block — its axes from 70 px high, its legend from 110 px (issue 185)
  const box = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(200);
  useEffect(() => {
    const element = box.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setHeight(entry?.contentRect.height ?? 0));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const axes = height >= 70;
  const legend = height >= 110;
  const value = (p: { seconds: number; plays: number }) =>
    metric === "time" ? Math.round((p.seconds / 3600) * 10) / 10 : p.plays;
  // the axis says its unit: « 1.5 h » (the hours in the viewer's language), a count of plays as is
  const tick = (n: number) => (metric === "time" ? format.hours(n) : format.number(n));
  const show = (n: number) =>
    metric === "time" ? measures.duration(n * 3600) : t("media:insights.plays", { count: n });
  // the axis keeps its dates short: the day and the month (the whole date in the tooltip)
  const label = (iso: string) => {
    if (unit === "month") return new Date(iso).toLocaleDateString(undefined, { month: "short" });
    const { day, month } = format.dayMonth(iso);
    return `${day} ${month}`;
  };
  if (chart === "donut") {
    const items = byKind.map((k) => ({ label: t(`media:insights.kind.${k.kind}`), value: value(k) }));
    return (
      <div className="widget-media-stats__donut">
        <DonutChart items={items} format={show} height={140} />
      </div>
    );
  }
  const rows = timeline.map((p) => ({ date: p.date, value: value(p) }));
  const series = [
    {
      key: "value",
      label: t(metric === "time" ? "media:widget.stats.hours" : "media:insights.metric.plays"),
    },
  ];
  return (
    <div ref={box} className="widget-media-stats__plot">
      {chart === "area" ? (
        <LinesChart
          data={rows}
          x="date"
          series={series}
          area
          height="100%"
          yAxis={axes}
          grid={axes}
          legend={legend}
          xAxis={axes}
          xFormat={label}
          yFormat={tick}
          format={show}
        />
      ) : (
        <BarsChart
          data={rows}
          x="date"
          series={series}
          height="100%"
          yAxis={axes}
          grid={axes}
          legend={legend}
          xAxis={axes}
          xFormat={label}
          yFormat={tick}
          format={show}
        />
      )}
    </div>
  );
}
