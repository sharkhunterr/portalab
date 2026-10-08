import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AdminEmpty } from "../../../design-system/admin/AdminKit";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { imageUrl } from "../api";
import { metadataImage } from "../detail/Enrichment";
import type { Breakdown, Film, Person, Production, Profile } from "./api";
import { useMeasures } from "./api";

/**
 * 027 — the charts of the statistics in depth (Telemetra-style): every figure next to the previous period
 * (grey or dashed), colors taken from the theme (``--chart-*``, ``--stream-*``, ``--quality-*``), a clock
 * and a week wheel for the viewing footprint, a world map of production countries.
 */
export const TOOLTIP = {
  background: "var(--color-surface-raised)",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-sm)",
};
const AXIS = { stroke: "var(--color-text-muted)", fontSize: 11 };
const PREVIOUS = "var(--chart-previous)";
const PALETTE = Array.from({ length: 8 }, (_, i) => `var(--chart-${i + 1})`);

/** A bucket's label: « Jan » for months, a short date otherwise. */
export function useBucketLabel(unit: "day" | "week" | "month") {
  const { locale } = useLocaleContext();
  const options: Intl.DateTimeFormatOptions =
    unit === "month"
      ? { month: "short", timeZone: "UTC" }
      : { day: "numeric", month: "short", timeZone: "UTC" };
  const formatter = new Intl.DateTimeFormat(locale, options);
  return (iso: string) => formatter.format(new Date(iso));
}

export function Legend({
  items,
}: {
  items: Array<{ key: string; label: string; color: string; dashed?: boolean }>;
}) {
  return (
    <p className="deep-legend">
      {items.map((item) => (
        <span key={item.key} className="deep-legend__item" data-dashed={item.dashed || undefined}>
          <span
            className="deep-legend__swatch"
            style={item.dashed ? undefined : { background: item.color }}
            aria-hidden="true"
          />
          {item.label}
        </span>
      ))}
    </p>
  );
}

/* ---------------------------------------------------------------- profile */

export function ActivityCompare({ data, metric }: { data: Profile; metric: "plays" | "completed" }) {
  const t = useT();
  const label = useBucketLabel(data.unit);
  const rows = data.buckets.map((bucket, i) => ({
    bucket,
    now: data.activity[i]?.[metric] ?? 0,
    before: metric === "plays" ? data.activity[i]?.previous_plays : data.activity[i]?.previous_completed,
  }));
  if (!rows.some((r) => r.now || r.before))
    return <AdminEmpty icon="chart" title={t("media:insights.none")} />;
  return (
    <figure className="deep-figure">
      <Legend
        items={[
          ...(data.has_previous
            ? [{ key: "p", label: t("media:deep.previous"), color: PREVIOUS, dashed: true }]
            : []),
          { key: "n", label: t("media:deep.current"), color: "var(--chart-1)" },
        ]}
      />
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
          <defs>
            <linearGradient id="deep-activity" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.45} />
              <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--color-border)" strokeDasharray="2 6" vertical={false} />
          <XAxis dataKey="bucket" tickFormatter={label} {...AXIS} minTickGap={18} />
          <YAxis {...AXIS} allowDecimals={false} />
          <Tooltip
            contentStyle={TOOLTIP}
            labelFormatter={(v) => label(String(v))}
            formatter={(value, name) => [
              value,
              name === "now" ? t("media:deep.current") : t("media:deep.previous"),
            ]}
          />
          {data.has_previous ? (
            <Line
              type="monotone"
              dataKey="before"
              stroke={PREVIOUS}
              strokeDasharray="5 5"
              dot={false}
              strokeWidth={1.5}
              isAnimationActive={false}
            />
          ) : null}
          <Area
            type="monotone"
            dataKey="now"
            stroke="var(--chart-1)"
            strokeWidth={2.5}
            fill="url(#deep-activity)"
            dot={{ r: 3, fill: "var(--color-surface)", stroke: "var(--chart-1)" }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </figure>
  );
}

const SUMMARY = [
  { key: "new", icon: "sparkles", tone: "ok" },
  { key: "rising", icon: "trending", tone: "info" },
  { key: "always", icon: "sync", tone: "neutral" },
  { key: "gone", icon: "arrow-down", tone: "bad" },
] as const;

export function GenreSummary({ data }: { data: Profile }) {
  const t = useT();
  return (
    <ul className="deep-summary">
      {SUMMARY.map((item) => {
        const names = data.summary[item.key];
        return (
          <li
            key={item.key}
            className="deep-summary__card"
            data-tone={item.tone}
            data-empty={!names.length || undefined}
          >
            <span className="deep-summary__count">
              {names.length}
              <Icon name={item.icon} size={16} />
            </span>
            <span className="deep-summary__text">
              <strong>{t(`media:deep.genres.${item.key}`)}</strong>
              <span className="deep-summary__hint">{t(`media:deep.genres.${item.key}Hint`)}</span>
              <span className="deep-chips">
                {names.slice(0, 6).map((name) => (
                  <span key={name} className="deep-chip">
                    {name}
                  </span>
                ))}
                {names.length > 6 ? <span className="deep-chips__more">+{names.length - 6}</span> : null}
                {!names.length ? <span className="deep-chips__more">—</span> : null}
              </span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export function GenreRadar({ data }: { data: Profile }) {
  const t = useT();
  const rows = data.genres.slice(0, 10).map((g) => ({ genre: g.name, now: g.count, before: g.previous }));
  if (rows.length < 3) return null;
  return (
    <figure className="deep-figure">
      <ResponsiveContainer width="100%" height={320}>
        <RadarChart data={rows} outerRadius="72%">
          <PolarGrid stroke="var(--color-border)" />
          <PolarAngleAxis dataKey="genre" tick={{ fill: "var(--color-text-muted)", fontSize: 11 }} />
          {data.has_previous ? (
            <Radar
              dataKey="before"
              stroke={PREVIOUS}
              strokeDasharray="4 4"
              fill="transparent"
              isAnimationActive={false}
            />
          ) : null}
          <Radar
            dataKey="now"
            stroke="var(--chart-1)"
            strokeWidth={2}
            fill="var(--chart-1)"
            fillOpacity={0.22}
            dot={{ r: 3, fill: "var(--chart-1)" }}
          />
          <Tooltip
            contentStyle={TOOLTIP}
            formatter={(value, name) => [
              value,
              name === "now" ? t("media:deep.current") : t("media:deep.previous"),
            ]}
          />
        </RadarChart>
      </ResponsiveContainer>
      <Legend
        items={[
          { key: "n", label: t("media:deep.current"), color: "var(--chart-1)" },
          ...(data.has_previous
            ? [{ key: "p", label: t("media:deep.previous"), color: PREVIOUS, dashed: true }]
            : []),
        ]}
      />
    </figure>
  );
}

export function GenreStack({ data }: { data: Profile }) {
  const t = useT();
  const label = useBucketLabel(data.unit);
  const keys = [...data.genre_series, ...(data.genre_buckets.some((b) => b.other) ? ["other"] : [])];
  const rows = data.buckets.map((bucket, i) => ({ bucket, ...data.genre_buckets[i] }));
  if (!keys.length) return <AdminEmpty icon="palette" title={t("media:insights.none")} />;
  const color = (key: string, i: number) =>
    key === "other" ? "var(--chart-other)" : (PALETTE[i % PALETTE.length] ?? "var(--chart-1)");
  return (
    <figure className="deep-figure">
      <Legend
        items={keys.map((key, i) => ({
          key,
          label: key === "other" ? t("media:deep.others") : key,
          color: color(key, i),
        }))}
      />
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
          <CartesianGrid stroke="var(--color-border)" strokeDasharray="2 6" vertical={false} />
          <XAxis dataKey="bucket" tickFormatter={label} {...AXIS} minTickGap={12} />
          <YAxis {...AXIS} allowDecimals={false} />
          <Tooltip
            contentStyle={TOOLTIP}
            labelFormatter={(v) => label(String(v))}
            formatter={(value, name) => [value, name === "other" ? t("media:deep.others") : String(name)]}
          />
          {keys.map((key, i) => (
            <Bar key={key} dataKey={key} stackId="g" fill={color(key, i)} isAnimationActive={false} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </figure>
  );
}

/** Hours of the day as a clock: one wedge per hour, as long as the plays started then. */
export function ClockWheel({ hours }: { hours: number[] }) {
  const t = useT();
  const max = Math.max(1, ...hours);
  const peak = hours.indexOf(Math.max(...hours));
  const wedge = (h: number) => {
    const inner = 34;
    const outer = inner + ((hours[h] ?? 0) / max) * 56;
    const a0 = ((h / 24) * 360 - 90 + 1.5) * (Math.PI / 180);
    const a1 = (((h + 1) / 24) * 360 - 90 - 1.5) * (Math.PI / 180);
    const p = (r: number, a: number) => `${100 + r * Math.cos(a)} ${100 + r * Math.sin(a)}`;
    return `M${p(inner, a0)} L${p(outer, a0)} A${outer} ${outer} 0 0 1 ${p(outer, a1)} L${p(inner, a1)} A${inner} ${inner} 0 0 0 ${p(inner, a0)}Z`;
  };
  return (
    <figure className="deep-wheel">
      <figcaption>{t("media:deep.hours")}</figcaption>
      <svg viewBox="0 0 200 200" role="img" aria-label={t("media:deep.hoursPeak", { hour: peak })}>
        {[34, 62, 90].map((r) => (
          <circle key={r} cx="100" cy="100" r={r} className="deep-wheel__ring" />
        ))}
        {hours.map((count, h) =>
          count ? (
            <path
              key={`hour-${String(h).padStart(2, "0")}`}
              d={wedge(h)}
              className="deep-wheel__wedge"
              style={{ opacity: 0.35 + (count / max) * 0.65 }}
            >
              <title>{`${h}h — ${count}`}</title>
            </path>
          ) : null,
        )}
        {[0, 6, 12, 18].map((h) => {
          const a = ((h / 24) * 360 - 90) * (Math.PI / 180);
          return (
            <text
              key={h}
              x={100 + 99 * Math.cos(a)}
              y={100 + 99 * Math.sin(a) + 3}
              className="deep-wheel__tick"
              data-peak={Math.floor(peak / 6) * 6 === h || undefined}
            >
              {String(h).padStart(2, "0")}
            </text>
          );
        })}
      </svg>
    </figure>
  );
}

/** Days of the week as a polar area: one slice per day, as deep as the plays that day. */
export function WeekWheel({ weekdays }: { weekdays: number[] }) {
  const t = useT();
  const measures = useMeasures();
  const max = Math.max(1, ...weekdays);
  const slice = (d: number) => {
    const inner = 26;
    const outer = inner + ((weekdays[d] ?? 0) / max) * 64;
    const a0 = ((d / 7) * 360 - 90 + 2) * (Math.PI / 180);
    const a1 = (((d + 1) / 7) * 360 - 90 - 2) * (Math.PI / 180);
    const p = (r: number, a: number) => `${100 + r * Math.cos(a)} ${100 + r * Math.sin(a)}`;
    return `M${p(inner, a0)} L${p(outer, a0)} A${outer} ${outer} 0 0 1 ${p(outer, a1)} L${p(inner, a1)} A${inner} ${inner} 0 0 0 ${p(inner, a0)}Z`;
  };
  return (
    <figure className="deep-wheel">
      <figcaption>{t("media:deep.weekdays")}</figcaption>
      <svg viewBox="0 0 200 200" role="img" aria-label={t("media:deep.weekdays")}>
        <circle cx="100" cy="100" r="90" className="deep-wheel__ring" />
        {weekdays.map((count, d) => {
          const a = (((d + 0.5) / 7) * 360 - 90) * (Math.PI / 180);
          return (
            <g key={measures.weekday(d + 1)}>
              <path d={slice(d)} className="deep-wheel__slice" style={{ opacity: 0.3 + (count / max) * 0.7 }}>
                <title>{`${measures.weekday(d + 1)} — ${count}`}</title>
              </path>
              <text x={100 + 99 * Math.cos(a)} y={100 + 99 * Math.sin(a) + 3} className="deep-wheel__tick">
                {measures.weekday(d + 1)}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

/* ---------------------------------------------------------------- casting */

export function Registry({ title, people, unit }: { title: string; people: Person[]; unit: string }) {
  const t = useT();
  const max = Math.max(1, ...people.map((p) => p.works));
  if (!people.length) return <AdminEmpty icon="users" title={t("media:deep.noPeople")} />;
  return (
    <div className="deep-registry">
      <p className="deep-registry__head">
        <span>{title}</span>
        <span className="deep-registry__sync">
          <span aria-hidden="true" /> {t("media:deep.sync")}
        </span>
      </p>
      <ol>
        {people.map((person, i) => {
          const portrait = metadataImage(person.image, "w185");
          const delta = person.works - person.previous;
          return (
            <li key={person.name} title={person.titles.join(" · ")}>
              <span className="deep-registry__rank">{String(i + 1).padStart(2, "0")}</span>
              <span className="deep-registry__portrait" aria-hidden="true">
                {portrait ? (
                  <img src={portrait} alt="" loading="lazy" />
                ) : (
                  person.name
                    .split(/\s+/)
                    .map((w) => w[0])
                    .join("")
                    .slice(0, 2)
                    .toUpperCase()
                )}
              </span>
              <span className="deep-registry__body">
                <span className="deep-registry__line">
                  <strong>{person.name}</strong>
                  <span className="deep-registry__count">
                    {t(unit, { count: person.works })}
                    {delta > 0 ? (
                      <span className="deep-delta" data-up="">
                        +{delta}
                      </span>
                    ) : null}
                  </span>
                </span>
                <span className="deep-registry__bar" aria-hidden="true">
                  <span style={{ inlineSize: `${(person.works / max) * 100}%` }} />
                </span>
                {person.titles.length ? (
                  <span className="deep-registry__titles">{person.titles.slice(0, 3).join(" · ")}</span>
                ) : null}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/* ---------------------------------------------------------------- production */

function poster(film: Film): string | null {
  return imageUrl(film.image_id) ?? metadataImage(film.poster_ref, "w185");
}

export function FinanceTiles({ data }: { data: Production }) {
  const t = useT();
  const measures = useMeasures();
  const tiles = [
    data.most_expensive
      ? {
          key: "expensive",
          icon: "coins",
          tone: "bad",
          value: measures.money(data.most_expensive.budget ?? 0),
          film: data.most_expensive,
        }
      : null,
    data.cheapest
      ? {
          key: "cheapest",
          icon: "arrow-down",
          tone: "neutral",
          value: measures.money(data.cheapest.budget ?? 0),
          film: data.cheapest,
        }
      : null,
    data.most_profitable
      ? {
          key: "profitable",
          icon: "trending",
          tone: "ok",
          value: `×${data.most_profitable.roi}`,
          film: data.most_profitable,
        }
      : null,
  ].filter((x) => x !== null);
  if (!tiles.length) return null;
  return (
    <ul className="deep-tiles">
      {tiles.map((tile) => (
        <li key={tile.key} className="deep-tile" data-tone={tile.tone}>
          <span className="deep-tile__label">{t(`media:deep.finance.${tile.key}`)}</span>
          <span className="deep-tile__value">
            <Icon name={tile.icon} size={20} />
            {tile.value}
          </span>
          <Link className="deep-tile__film" to={`/media/${tile.film.id}`}>
            {tile.film.title}
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function CompareBars({
  rows,
  hasPrevious,
  label = (v) => v,
  averages,
  height = 220,
}: {
  rows: Array<{ key: string; count: number; previous: number }>;
  hasPrevious: boolean;
  label?: (key: string) => string;
  averages?: { now: number | null; before: number | null };
  height?: number;
}) {
  const t = useT();
  return (
    <figure className="deep-figure">
      <Legend
        items={[
          ...(hasPrevious ? [{ key: "p", label: t("media:deep.previous"), color: PREVIOUS }] : []),
          { key: "n", label: t("media:deep.current"), color: "var(--chart-1)" },
        ]}
      />
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={rows} margin={{ top: 22, right: 8, bottom: 0, left: -18 }} barGap={3}>
          <CartesianGrid stroke="var(--color-border)" strokeDasharray="2 6" vertical={false} />
          <XAxis dataKey="key" tickFormatter={label} {...AXIS} minTickGap={6} />
          <YAxis {...AXIS} allowDecimals={false} />
          <Tooltip
            contentStyle={TOOLTIP}
            labelFormatter={(v) => label(String(v))}
            formatter={(value, name) => [
              value,
              name === "count" ? t("media:deep.current") : t("media:deep.previous"),
            ]}
          />
          {hasPrevious ? (
            <Bar dataKey="previous" fill={PREVIOUS} radius={[2, 2, 0, 0]} isAnimationActive={false} />
          ) : null}
          <Bar dataKey="count" fill="var(--chart-1)" radius={[2, 2, 0, 0]} />
          {averages?.before && Math.round(averages.before) !== Math.round(averages.now ?? 0) ? (
            <ReferenceLine
              x={String(Math.round(averages.before))}
              stroke={PREVIOUS}
              strokeDasharray="4 4"
              label={{
                value: t("media:deep.avg", { value: Math.round(averages.before) }),
                fill: "var(--color-text-muted)",
                fontSize: 10,
                position: "insideTopLeft",
              }}
            />
          ) : null}
          {averages?.now ? (
            <ReferenceLine
              x={String(Math.round(averages.now))}
              stroke="var(--chart-1)"
              strokeDasharray="4 4"
              label={{
                value: t("media:deep.avg", { value: Math.round(averages.now) }),
                fill: "var(--chart-1)",
                fontSize: 10,
                position: "insideTopRight",
              }}
            />
          ) : null}
        </BarChart>
      </ResponsiveContainer>
    </figure>
  );
}

export function RoiList({ films, tone }: { films: Film[]; tone: "ok" | "bad" }) {
  const t = useT();
  const measures = useMeasures();
  const format = useFormat();
  if (!films.length) return <AdminEmpty icon="coins" title={t("media:deep.noMoney")} />;
  return (
    <ol className="deep-roi" data-tone={tone}>
      {films.map((film, i) => {
        const art = poster(film);
        const gain = film.roi !== null ? film.roi - 1 : null;
        return (
          <li key={film.id}>
            <span className="deep-roi__rank">{String(i + 1).padStart(2, "0")}</span>
            <span className="deep-roi__art" aria-hidden="true">
              {art ? <img src={art} alt="" loading="lazy" /> : <Icon name="film" size={18} />}
            </span>
            <Link to={`/media/${film.id}`} className="deep-roi__title">
              {film.title}
            </Link>
            <span className="deep-roi__cell">
              <span>{t("media:deep.budget")}</span>
              <strong>{film.budget ? measures.money(film.budget) : "—"}</strong>
            </span>
            <Icon name="chevron-right" size={14} />
            <span className="deep-roi__cell" data-accent="">
              <span>{t("media:deep.revenue")}</span>
              <strong>{film.revenue ? measures.money(film.revenue) : "—"}</strong>
            </span>
            <Icon name="chevron-right" size={14} />
            <span className="deep-roi__cell" data-accent="">
              <span>{t("media:deep.roi")}</span>
              <strong>×{film.roi}</strong>
              {gain !== null ? (
                <small>
                  {gain >= 0 ? "+" : "−"}
                  {format.percent(Math.abs(gain))}
                </small>
              ) : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

interface WorldMap {
  w: number;
  h: number;
  countries: Record<string, { d: string; x: number; y: number; name: string }>;
  rest: string;
}

/** Where the films come from: the countries tinted by how many, the main ones labelled. */
export function CountryMap({ countries }: { countries: Array<{ code: string; count: number }> }) {
  const t = useT();
  const { locale } = useLocaleContext();
  const [map, setMap] = useState<WorldMap | null>(null);
  useEffect(() => {
    let live = true;
    void import("./world-map.json").then((module) => {
      if (live) setMap(module.default as WorldMap);
    });
    return () => {
      live = false;
    };
  }, []);
  const names = useMemo(() => {
    try {
      return new Intl.DisplayNames([locale], { type: "region" });
    } catch {
      return null;
    }
  }, [locale]);
  const counts = new Map(countries.map((c) => [c.code === "UK" ? "GB" : c.code, c.count]));
  const max = Math.max(1, ...countries.map((c) => c.count));
  const labelled = countries.slice(0, 7);
  if (!countries.length) return <AdminEmpty icon="globe" title={t("media:insights.none")} />;
  return (
    <figure className="deep-map">
      {map ? (
        <svg viewBox={`0 0 ${map.w} ${map.h}`} role="img" aria-label={t("media:deep.countries")}>
          <path d={map.rest} className="deep-map__land" />
          {Object.entries(map.countries).map(([code, country]) => {
            const count = counts.get(code);
            return (
              <path
                key={code}
                d={country.d}
                className="deep-map__land"
                data-on={count ? "" : undefined}
                style={count ? { fillOpacity: 0.25 + (count / max) * 0.75 } : undefined}
              >
                <title>{`${names?.of(code) ?? country.name}${count ? ` — ${count}` : ""}`}</title>
              </path>
            );
          })}
          {(() => {
            // the main countries called out in two columns, on the side of the map they are on
            const placed = labelled
              .map((c) => ({ ...c, at: map.countries[c.code === "UK" ? "GB" : c.code] }))
              .filter((c) => c.at)
              .sort((a, b) => (a.at?.y ?? 0) - (b.at?.y ?? 0));
            const slots = { left: 0, right: 0 };
            return placed.map((c) => {
              const country = c.at as { x: number; y: number; name: string };
              const side = country.x < map.w / 2 ? "left" : "right";
              const row = slots[side]++;
              const bx = side === "left" ? 6 : map.w - 156;
              const by = 10 + row * 34;
              const name = (names?.of(c.code) ?? country.name).toUpperCase();
              return (
                <g key={c.code} className="deep-map__tag">
                  <polyline
                    points={`${country.x},${country.y} ${side === "left" ? bx + 170 : bx - 14},${by + 13} ${side === "left" ? bx + 150 : bx},${by + 13}`}
                  />
                  <circle cx={country.x} cy={country.y} r="4" />
                  <rect x={bx} y={by} width="150" height="26" rx="2" />
                  <text x={bx + 8} y={by + 17}>
                    {name.length > 15 ? `${name.slice(0, 14)}…` : name}
                  </text>
                  <text x={bx + 142} y={by + 17} className="deep-map__count">
                    {c.count}
                  </text>
                </g>
              );
            });
          })()}
        </svg>
      ) : (
        <div className="deep-map__loading" />
      )}
    </figure>
  );
}

/* ---------------------------------------------------------------- playback */

export const STREAM_COLORS: Record<string, string> = {
  direct: "var(--stream-direct)",
  copy: "var(--stream-copy)",
  transcode: "var(--stream-transcode)",
  unknown: "var(--chart-other)",
};
export const QUALITY_COLORS: Record<string, string> = {
  "4k": "var(--quality-4k)",
  "1080p": "var(--quality-1080)",
  "720p": "var(--quality-720)",
  sd: "var(--quality-sd)",
  unknown: "var(--chart-other)",
};

/** A donut with its center figure and its slices called out. */
export function Donut({
  slices,
  total,
  caption,
  colors,
  label,
}: {
  slices: Array<{ key: string; value: number }>;
  total: number;
  caption: string;
  colors: (key: string, i: number) => string;
  label: (key: string) => string;
}) {
  const format = useFormat();
  const shown = slices.filter((s) => s.value > 0);
  return (
    <figure className="deep-donut">
      <div className="deep-donut__chart">
        <ResponsiveContainer width="100%" height={190}>
          <PieChart>
            <Pie
              data={shown.length ? shown : [{ key: "none", value: 1 }]}
              dataKey="value"
              nameKey="key"
              innerRadius="68%"
              outerRadius="92%"
              paddingAngle={shown.length > 1 ? 2 : 0}
              stroke="none"
              isAnimationActive={false}
            >
              {(shown.length ? shown : [{ key: "none", value: 1 }]).map((slice, i) => (
                <Cell key={slice.key} fill={shown.length ? colors(slice.key, i) : "var(--color-border)"} />
              ))}
            </Pie>
            <Tooltip contentStyle={TOOLTIP} formatter={(value, name) => [value, label(String(name))]} />
          </PieChart>
        </ResponsiveContainer>
        <span className="deep-donut__center">
          <strong>{format.number(total)}</strong>
          <span>{caption}</span>
        </span>
      </div>
      <ul className="deep-donut__callouts">
        {shown.map((slice, i) => (
          <li key={slice.key} style={{ borderColor: colors(slice.key, i) }}>
            <span>{label(slice.key)}</span>
            <strong style={{ color: colors(slice.key, i) }}>{format.number(slice.value)}</strong>
          </li>
        ))}
      </ul>
    </figure>
  );
}

/** Per bucket: this period's breakdown stacked, next to the previous period's total in grey. */
export function BreakdownBars({
  data,
  buckets,
  unit,
  hasPrevious,
  colors,
  label,
}: {
  data: Breakdown;
  buckets: string[];
  unit: "day" | "week" | "month";
  hasPrevious: boolean;
  colors: Record<string, string>;
  label: (key: string) => string;
}) {
  const t = useT();
  const bucketLabel = useBucketLabel(unit);
  const keys = data.totals.map((x) => x.key);
  const rows = buckets.map((bucket, i) => ({
    bucket,
    ...data.series[i]?.current,
    previous: Object.values(data.series[i]?.previous ?? {}).reduce((a, b) => a + b, 0),
  }));
  if (!keys.length) return <AdminEmpty icon="chart" title={t("media:insights.none")} />;
  return (
    <figure className="deep-figure">
      <Legend
        items={[
          ...keys.map((key) => ({ key, label: label(key), color: colors[key] ?? "var(--chart-other)" })),
          ...(hasPrevious ? [{ key: "p", label: t("media:deep.previousTotal"), color: PREVIOUS }] : []),
        ]}
      />
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -18 }} barGap={2}>
          <CartesianGrid stroke="var(--color-border)" strokeDasharray="2 6" vertical={false} />
          <XAxis dataKey="bucket" tickFormatter={bucketLabel} {...AXIS} minTickGap={12} />
          <YAxis {...AXIS} allowDecimals={false} />
          <Tooltip
            contentStyle={TOOLTIP}
            labelFormatter={(v) => bucketLabel(String(v))}
            formatter={(value, name) => [
              value,
              name === "previous" ? t("media:deep.previousTotal") : label(String(name)),
            ]}
          />
          {keys.map((key) => (
            <Bar
              key={key}
              dataKey={key}
              stackId="now"
              fill={colors[key] ?? "var(--chart-other)"}
              isAnimationActive={false}
            />
          ))}
          {hasPrevious ? <Bar dataKey="previous" fill={PREVIOUS} isAnimationActive={false} /> : null}
        </BarChart>
      </ResponsiveContainer>
    </figure>
  );
}
