import type { ReactNode } from "react";
import { AdminPage, AdminSection } from "../../../design-system/admin/AdminKit";
import {
  BarsChart,
  DonutChart,
  GaugeChart,
  HeatmapChart,
  LinesChart,
  RadarProfile,
  Sparkline,
} from "../../../design-system/charts/Charts";
import {
  DumbbellChart,
  FunnelSteps,
  LollipopChart,
  MirrorBars,
  PolarWheel,
  RingsChart,
  StackedColumns,
  StackedProgress,
  SunburstChart,
  WaffleChart,
} from "../../../design-system/charts/Shapes";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import "./chart-gallery.css";

/**
 * The chart gallery (issue 117): every shape of the chart kit, drawn in the current theme with sample data,
 * each with what it is for — to choose one for a page or a widget, and to see a theme's colours at work.
 */
// a week from Monday, named in the member's language
const DAYS = Array.from({ length: 7 }, (_, i) =>
  new Date(Date.UTC(2026, 9, 12 + i, 12)).toLocaleDateString(undefined, { weekday: "short" }),
);
const WEEK = DAYS.map((day, i) => ({
  day,
  films: [2, 0, 3, 1, 2, 5, 4][i] ?? 0,
  series: [1, 2, 1, 3, 2, 3, 2][i] ?? 0,
  books: [0, 1, 0, 1, 1, 2, 1][i] ?? 0,
}));
const MONTH = Array.from({ length: 30 }, (_, i) => ({
  day: `${i + 1}`,
  xp: Math.round(120 + 90 * Math.sin(i / 4) + i * 6),
  coins: Math.round(30 + 20 * Math.cos(i / 5) + i),
}));
const RUNNING = MONTH.map((point, i) => ({
  day: point.day,
  total: MONTH.slice(0, i + 1).reduce((sum, p) => sum + p.xp, 0),
}));
const MEMBERS = [
  { name: "Morgane", plays: 320, quests: 140, achievements: 60 },
  { name: "Thibaut", plays: 260, quests: 180, achievements: 40 },
  { name: "Léa", plays: 190, quests: 90, achievements: 80 },
  { name: "Alex", plays: 150, quests: 60, achievements: 20 },
];
const HOURS = ["0h", "3h", "6h", "9h", "12h", "15h", "18h", "21h"];
const HEAT = DAYS.map((_, d) =>
  HOURS.map((_, h) => Math.max(0, Math.round(6 * Math.sin((h + d) / 2) + (h > 5 ? 6 : 0)))),
);

const CLOCK = Array.from({ length: 24 }, (_, h) =>
  Math.round(2 + 10 * Math.max(0, Math.sin((h - 6) / 5)) + (h >= 20 ? 6 : 0)),
);

export default function ChartGallery() {
  const t = useT();
  const format = useFormat();
  const n = (value: number) => format.number(value);
  const card = (key: string, chart: ReactNode) => (
    <AdminSection
      key={key}
      icon="chart"
      title={t(`admin:charts.kind.${key}.title`)}
      description={t(`admin:charts.kind.${key}.use`)}
    >
      {chart}
    </AdminSection>
  );
  const kinds = {
    films: t("admin:charts.sample.films"),
    series: t("admin:charts.sample.series"),
    books: t("admin:charts.sample.books"),
  };
  return (
    <AdminPage icon="chart" title={t("admin:charts.title")} description={t("admin:charts.description")} wide>
      <div className="admin-grid">
        {card(
          "bars",
          <BarsChart data={WEEK} x="day" series={[{ key: "films", label: kinds.films }]} format={n} />,
        )}
        {card(
          "stacked",
          <BarsChart
            data={WEEK}
            x="day"
            stacked
            series={[
              { key: "films", label: kinds.films },
              { key: "series", label: kinds.series },
              { key: "books", label: kinds.books },
            ]}
            format={n}
          />,
        )}
        {card(
          "horizontal",
          <BarsChart
            data={MEMBERS}
            x="name"
            horizontal
            stacked
            series={[
              { key: "plays", label: t("admin:charts.sample.plays") },
              { key: "quests", label: t("admin:charts.sample.quests") },
              { key: "achievements", label: t("admin:charts.sample.achievements") },
            ]}
            format={n}
          />,
        )}
        {card(
          "lines",
          <LinesChart
            data={MONTH}
            x="day"
            series={[
              { key: "xp", label: "XP" },
              { key: "coins", label: t("admin:charts.sample.coins"), dashed: true },
            ]}
            format={n}
          />,
        )}
        {card(
          "area",
          <LinesChart
            data={RUNNING}
            x="day"
            area
            series={[{ key: "total", label: t("admin:charts.sample.total") }]}
            format={n}
          />,
        )}
        {card(
          "donut",
          <DonutChart
            items={[
              { label: kinds.films, value: 42 },
              { label: kinds.series, value: 31 },
              { label: kinds.books, value: 14 },
              { label: t("admin:charts.sample.music"), value: 9 },
            ]}
            totalLabel={t("admin:charts.sample.plays")}
            format={n}
          />,
        )}
        {card(
          "gauge",
          <GaugeChart value={1240} max={1900} label={t("admin:charts.sample.level")} format={n} />,
        )}
        {card(
          "sparkline",
          <div className="chart-gallery__sparks">
            {[
              [kinds.films, [3, 4, 2, 6, 5, 8, 7]],
              [kinds.series, [6, 5, 5, 4, 3, 3, 2]],
              ["XP", [10, 30, 25, 60, 55, 90, 120]],
            ].map(([name, values], index) => (
              <div key={String(name)} className="chart-gallery__spark">
                <span>{String(name)}</span>
                <Sparkline
                  values={values as number[]}
                  label={String(name)}
                  color={["var(--color-accent)", "var(--color-accent-alt)", "var(--rarity-epic)"][index]}
                />
              </div>
            ))}
          </div>,
        )}
        {card(
          "heatmap",
          <HeatmapChart
            rows={DAYS}
            columns={HOURS}
            values={HEAT}
            label={t("admin:charts.kind.heatmap.title")}
          />,
        )}
        {card(
          "radar",
          <RadarProfile
            axes={[
              t("admin:charts.sample.action"),
              t("admin:charts.sample.comedy"),
              t("admin:charts.sample.drama"),
              t("admin:charts.sample.horror"),
              t("admin:charts.sample.scifi"),
              t("admin:charts.sample.animation"),
            ]}
            series={[
              { label: t("admin:charts.sample.me"), values: [8, 5, 7, 2, 9, 4] },
              { label: t("admin:charts.sample.average"), values: [6, 6, 5, 4, 6, 5] },
            ]}
          />,
        )}
        {card(
          "clock",
          <PolarWheel
            values={CLOCK}
            labels={CLOCK.map((_, h) => String(h).padStart(2, "0"))}
            every={3}
            label={t("admin:charts.kind.clock.title")}
          />,
        )}
        {card(
          "week",
          <PolarWheel
            values={[4, 3, 5, 4, 7, 12, 10]}
            labels={DAYS}
            color="var(--color-accent-alt)"
            label={t("admin:charts.kind.week.title")}
          />,
        )}
        {card(
          "rings",
          <RingsChart
            items={[
              { label: kinds.films, value: 82 },
              { label: kinds.series, value: 64 },
              { label: kinds.books, value: 41 },
              { label: t("admin:charts.sample.music"), value: 23 },
            ]}
          />,
        )}
        {card(
          "stack",
          <div className="chart-gallery__stacks">
            <StackedProgress
              label={t("admin:charts.kind.stack.title")}
              total={1200}
              items={[
                { label: kinds.films, value: 420 },
                { label: kinds.series, value: 310 },
                { label: kinds.books, value: 140 },
              ]}
              format={n}
            />
            <StackedProgress
              vertical
              label={t("admin:charts.kind.stack.title")}
              items={[
                { label: t("admin:charts.sample.plays"), value: 520 },
                { label: t("admin:charts.sample.quests"), value: 260 },
                { label: t("admin:charts.sample.achievements"), value: 90 },
              ]}
              format={n}
            />
          </div>,
        )}
        {card(
          "columns",
          <StackedColumns
            label={t("admin:charts.kind.columns.title")}
            groups={MEMBERS.map((m) => ({
              label: m.name,
              items: [
                { label: t("admin:charts.sample.plays"), value: m.plays },
                { label: t("admin:charts.sample.quests"), value: m.quests },
                { label: t("admin:charts.sample.achievements"), value: m.achievements },
              ],
            }))}
            format={n}
          />,
        )}
        {card(
          "waffle",
          <div className="chart-gallery__waffles">
            <WaffleChart value={68} label={t("admin:charts.sample.finished")} />
            <WaffleChart
              value={23}
              label={t("admin:charts.sample.requested")}
              color="var(--color-accent-alt)"
            />
          </div>,
        )}
        {card(
          "mirror",
          <MirrorBars
            left={{ label: t("admin:charts.sample.me") }}
            right={{ label: t("admin:charts.sample.average") }}
            rows={[
              { label: t("admin:charts.sample.action"), left: 14, right: 9 },
              { label: t("admin:charts.sample.comedy"), left: 6, right: 11 },
              { label: t("admin:charts.sample.drama"), left: 10, right: 8 },
              { label: t("admin:charts.sample.horror"), left: 2, right: 5 },
              { label: t("admin:charts.sample.scifi"), left: 12, right: 7 },
            ]}
            format={n}
          />,
        )}
        {card(
          "dumbbell",
          <DumbbellChart
            before={t("admin:charts.sample.lastMonth")}
            after={t("admin:charts.sample.thisMonth")}
            rows={[
              { label: kinds.films, before: 12, after: 19 },
              { label: kinds.series, before: 30, after: 22 },
              { label: kinds.books, before: 4, after: 9 },
              { label: t("admin:charts.sample.music"), before: 40, after: 46 },
            ]}
            format={n}
          />,
        )}
        {card(
          "lollipop",
          <LollipopChart
            rows={MEMBERS.map((m) => ({ label: m.name, value: m.plays + m.quests + m.achievements }))}
            format={n}
          />,
        )}
        {card(
          "funnel",
          <FunnelSteps
            steps={[
              { label: t("admin:charts.sample.requested"), value: 120 },
              { label: t("admin:charts.sample.available"), value: 96 },
              { label: t("admin:charts.sample.started"), value: 71 },
              { label: t("admin:charts.sample.finished"), value: 52 },
            ]}
            format={n}
          />,
        )}
        {card(
          "sunburst",
          <SunburstChart
            groups={[
              {
                label: kinds.films,
                children: [
                  { label: t("admin:charts.sample.action"), value: 30 },
                  { label: t("admin:charts.sample.drama"), value: 22 },
                  { label: t("admin:charts.sample.comedy"), value: 14 },
                ],
              },
              {
                label: kinds.series,
                children: [
                  { label: t("admin:charts.sample.scifi"), value: 25 },
                  { label: t("admin:charts.sample.animation"), value: 12 },
                ],
              },
              {
                label: kinds.books,
                children: [
                  { label: t("admin:charts.sample.horror"), value: 9 },
                  { label: t("admin:charts.sample.drama"), value: 7 },
                ],
              },
            ]}
            format={n}
          />,
        )}
      </div>
    </AdminPage>
  );
}
