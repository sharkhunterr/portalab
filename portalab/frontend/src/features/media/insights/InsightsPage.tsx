import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  AdminEmpty,
  AdminGrid,
  AdminPage,
  AdminSection,
  AdminStats,
  AdminTable,
  AdminTabs,
} from "../../../design-system/admin/AdminKit";
import { SelectField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { imageUrl } from "../api";
import {
  CATEGORIES,
  type Category,
  type Insights,
  PERIODS,
  type Ranked,
  type Scope,
  useInsights,
  useMeasures,
} from "./api";
import "../../admin/admin.css";
import "./insights.css";

/**
 * Media statistics (027 — « like Telemetra, but better »): time spent, plays, titles and active days with
 * their trend; the activity over time by kind; when (weekday × hour); the top titles with their posters;
 * genres, people, decades, records, the box office of the films watched, requests and devices. « Me » or
 * the whole server (anonymous for members; members, devices and ingestion sources for media managers).
 */
const KIND_ORDER = ["movie", "episode", "live", "track", "book", "audiobook", "other"];

function Trend({ now, before }: { now: number; before: number | undefined }) {
  const t = useT();
  const format = useFormat();
  if (before === undefined || before === 0) return null;
  const ratio = (now - before) / before;
  const tone = ratio > 0.02 ? "up" : ratio < -0.02 ? "down" : "flat";
  return (
    <span className="insights-trend" data-trend={tone}>
      <Icon name={tone === "up" ? "arrow-up" : tone === "down" ? "arrow-down" : "minus"} size={14} />
      {t("media:insights.trend", { value: format.percent(Math.abs(ratio)) })}
    </span>
  );
}

function Timeline({ data }: { data: Insights }) {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  const kinds = KIND_ORDER.filter((k) => data.timeline.points.some((p) => p.seconds[k]));
  const rows = data.timeline.points.map((p) => ({
    label: p.date,
    ...Object.fromEntries(kinds.map((k) => [k, Math.round(((p.seconds[k] ?? 0) / 3600) * 10) / 10])),
  }));
  const label = (iso: string) =>
    data.timeline.unit === "month"
      ? new Date(iso).toLocaleDateString(undefined, { month: "short", year: "2-digit" })
      : format.date(iso, "short");
  if (!rows.some((r) => kinds.some((k) => (r as Record<string, number | string>)[k]))) {
    return <AdminEmpty icon="chart" title={t("media:insights.none")} />;
  }
  return (
    <figure className="insights-chart">
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
          <XAxis
            dataKey="label"
            tickFormatter={label}
            stroke="var(--color-text-muted)"
            fontSize={12}
            minTickGap={24}
          />
          <YAxis stroke="var(--color-text-muted)" fontSize={12} allowDecimals={false} />
          <Tooltip
            labelFormatter={(value) => label(String(value))}
            formatter={(value, name) => [
              measures.duration(Number(value) * 3600),
              t(`media:insights.kind.${String(name)}`),
            ]}
            contentStyle={{
              background: "var(--color-surface-raised)",
              border: "1px solid var(--color-border)",
            }}
          />
          {kinds.map((kind) => (
            <Bar
              key={kind}
              dataKey={kind}
              stackId="a"
              fill={`var(--kind-${kind})`}
              radius={[3, 3, 0, 0]}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <figcaption className="insights-legend">
        {kinds.map((kind) => (
          <span key={kind} className="insights-legend__item" data-kind={kind}>
            {t(`media:insights.kind.${kind}`)}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}

function Heatmap({ data }: { data: Insights }) {
  const t = useT();
  const measures = useMeasures();
  const cells = new Map(data.heatmap.map((c) => [`${c.weekday}-${c.hour}`, c]));
  // intensity by time spent, or by plays when the sources gave no durations
  const bySeconds = data.heatmap.some((c) => c.seconds > 0);
  const amount = (c: { seconds: number; plays: number }) => (bySeconds ? c.seconds : c.plays);
  const max = Math.max(1, ...data.heatmap.map(amount));
  const hours = Array.from({ length: 24 }, (_, h) => h);
  if (!data.heatmap.length) return <AdminEmpty icon="clock" title={t("media:insights.none")} />;
  return (
    <div className="insights-heatmap">
      <table>
        <caption className="visually-hidden">{t("media:insights.when")}</caption>
        <thead>
          <tr>
            <th scope="col">
              <span className="visually-hidden">{t("media:insights.weekday")}</span>
            </th>
            {hours.map((h) => (
              <th key={h} scope="col" className="insights-heatmap__hour">
                {h % 6 === 0 ? h : <span className="visually-hidden">{h}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {[1, 2, 3, 4, 5, 6, 7].map((day) => (
            <tr key={day}>
              <th scope="row" className="insights-heatmap__day">
                {measures.weekday(day)}
              </th>
              {hours.map((h) => {
                const cell = cells.get(`${day}-${h}`);
                const level = cell ? Math.ceil((amount(cell) / max) * 4) : 0;
                return (
                  <td
                    key={h}
                    className="insights-heatmap__cell"
                    data-level={level}
                    title={
                      cell ? `${measures.weekday(day)} ${h}h — ${measures.duration(cell.seconds)}` : undefined
                    }
                  >
                    <span className="visually-hidden">{cell ? measures.duration(cell.seconds) : "—"}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Bars({
  rows,
  value,
}: {
  rows: Array<{ key: string; label: string; amount: number; hint?: string }>;
  value: (n: number) => string;
}) {
  const max = Math.max(1, ...rows.map((r) => r.amount));
  return (
    <ol className="insights-bars">
      {rows.map((row) => (
        <li key={row.key}>
          <span className="insights-bars__label">
            {row.label}
            {row.hint ? <span className="admin-muted"> · {row.hint}</span> : null}
          </span>
          <span className="insights-bars__value">{value(row.amount)}</span>
          <span className="insights-bars__track" aria-hidden="true">
            <span className="insights-bars__fill" style={{ inlineSize: `${(row.amount / max) * 100}%` }} />
          </span>
        </li>
      ))}
    </ol>
  );
}

function TopWorks({ data }: { data: Insights }) {
  const t = useT();
  const measures = useMeasures();
  if (!data.top_works.length) return <AdminEmpty icon="trophy" title={t("media:insights.none")} />;
  return (
    <ol className="insights-posters">
      {data.top_works.map((work, index) => {
        const poster = imageUrl(work.image_id);
        const body = (
          <>
            <span className="insights-poster__art">
              {poster ? <img src={poster} alt="" loading="lazy" /> : <Icon name="film" size={28} />}
              <span className="insights-poster__rank">{index + 1}</span>
            </span>
            <span className="insights-poster__title">{work.title}</span>
            <span className="insights-poster__meta">
              {measures.duration(work.seconds)} · {t("media:insights.plays", { count: work.plays })}
              {work.members ? ` · ${t("media:insights.membersCount", { count: work.members })}` : ""}
            </span>
          </>
        );
        return (
          <li key={work.id ?? work.title} className="insights-poster">
            {work.id ? <Link to={`/media/${work.id}`}>{body}</Link> : <span>{body}</span>}
          </li>
        );
      })}
    </ol>
  );
}

function ranked(rows: Ranked[], t: ReturnType<typeof useT>) {
  return rows.map((r) => ({
    key: r.name,
    label: r.name,
    amount: r.seconds,
    hint: r.works
      ? t("media:insights.titlesCount", { count: r.works })
      : t("media:insights.plays", { count: r.plays }),
  }));
}

function Records({ data }: { data: Insights }) {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  const r = data.records;
  const items = [
    r.longest
      ? {
          key: "longest",
          icon: "clock",
          label: t("media:insights.records.longest"),
          value: measures.duration(r.longest.seconds),
          hint: r.longest.parent_title ? `${r.longest.parent_title} — ${r.longest.title}` : r.longest.title,
        }
      : null,
    r.busiest_day
      ? {
          key: "busiest",
          icon: "zap",
          label: t("media:insights.records.busiest"),
          value: measures.duration(r.busiest_day.seconds),
          hint: format.date(r.busiest_day.date, "long"),
        }
      : null,
    {
      key: "streak",
      icon: "target",
      label: t("media:insights.records.streak"),
      value: t("media:insights.daysCount", { count: r.best_streak }),
      hint: null,
    },
    {
      key: "completed",
      icon: "check",
      label: t("media:insights.records.completed"),
      value: format.number(r.completed),
      hint: r.first_at ? t("media:insights.records.since", { date: format.date(r.first_at) }) : null,
    },
  ].filter((x) => x !== null);
  return (
    <ul className="insights-records">
      {items.map((item) => (
        <li key={item.key}>
          <Icon name={item.icon} size={20} />
          <span className="insights-records__label">{item.label}</span>
          <strong className="insights-records__value">{item.value}</strong>
          {item.hint ? <span className="admin-muted insights-records__hint">{item.hint}</span> : null}
        </li>
      ))}
    </ul>
  );
}

function BoxOffice({ data }: { data: NonNullable<Insights["box_office"]> }) {
  const t = useT();
  const measures = useMeasures();
  return (
    <div className="insights-box">
      <p className="insights-box__figures">
        <span>
          <span className="admin-muted">{t("media:insights.box.revenue")}</span>
          <strong>{measures.money(data.revenue)}</strong>
        </span>
        <span>
          <span className="admin-muted">{t("media:insights.box.budget")}</span>
          <strong>{measures.money(data.budget)}</strong>
        </span>
        <span>
          <span className="admin-muted">{t("media:insights.box.films")}</span>
          <strong>{data.films}</strong>
        </span>
      </p>
      {data.top.length ? (
        <ol className="insights-box__top">
          {data.top.map((film) => (
            <li key={film.id}>
              <Link to={`/media/${film.id}`}>{film.title}</Link>
              <span className="admin-muted">{measures.money(film.revenue)}</span>
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}

export default function InsightsPage() {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  const [params, setParams] = useSearchParams();
  const scope: Scope = params.get("scope") === "all" ? "all" : "me";
  const category = (CATEGORIES as string[]).includes(params.get("category") ?? "")
    ? (params.get("category") as Category)
    : "all";
  const [period, setPeriod] = useState(params.get("period") ?? "30d");
  const insights = useInsights(scope, category, period);
  const set = (key: string, value: string, fallback: string) => {
    const next = new URLSearchParams(params);
    if (value === fallback) next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };
  const years = Array.from({ length: 4 }, (_, i) => String(new Date().getFullYear() - i));
  const data = insights.data;
  return (
    <AdminPage
      icon="chart"
      title={t("media:insights.title")}
      description={t(scope === "me" ? "media:insights.subtitleMe" : "media:insights.subtitleAll")}
      tabs={
        <AdminTabs
          label={t("media:insights.title")}
          current={scope}
          onChange={(next) => set("scope", next, "me")}
          tabs={[
            { key: "me", label: t("media:insights.scope.me") },
            { key: "all", label: t("media:insights.scope.all") },
          ]}
        />
      }
      secondary={
        <SelectField
          label={t("media:insights.period")}
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
        >
          {PERIODS.map((p) => (
            <option key={p} value={p}>
              {t(`media:insights.periods.${p}`)}
            </option>
          ))}
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </SelectField>
      }
    >
      <AdminTabs
        label={t("media:insights.category")}
        current={category}
        onChange={(next) => set("category", next, "all")}
        tabs={CATEGORIES.map((c) => ({ key: c, label: t(`media:insights.categories.${c}`) }))}
      />
      {insights.isPending ? <FunctionalState state="loading" /> : null}
      {insights.isError ? <FunctionalState state="error" onRetry={() => insights.refetch()} /> : null}
      {data ? (
        <>
          <AdminStats
            label={t("media:insights.title")}
            stats={[
              {
                key: "time",
                label: t("media:insights.stat.time"),
                value: measures.duration(data.totals.seconds),
                hint: <Trend now={data.totals.seconds} before={data.previous?.seconds} />,
                icon: "clock",
                tone: "info",
              },
              {
                key: "plays",
                label: t("media:insights.stat.plays"),
                value: format.number(data.totals.plays),
                hint: <Trend now={data.totals.plays} before={data.previous?.plays} />,
                icon: "activity",
                tone: "info",
              },
              {
                key: "works",
                label: t("media:insights.stat.works"),
                value: format.number(data.totals.works),
                hint: t("media:insights.completedCount", { count: data.totals.completed }),
                icon: "film",
                tone: "neutral",
              },
              data.totals.members !== null
                ? {
                    key: "members",
                    label: t("media:insights.stat.members"),
                    value: format.number(data.totals.members),
                    icon: "users",
                    tone: "neutral" as const,
                  }
                : {
                    key: "days",
                    label: t("media:insights.stat.days"),
                    value: format.number(data.totals.active_days),
                    icon: "calendar",
                    tone: "neutral" as const,
                  },
            ]}
          />
          {data.totals.plays === 0 ? (
            <AdminEmpty
              icon="chart"
              title={t("media:insights.empty")}
              action={<span className="admin-muted">{t("media:insights.emptyHint")}</span>}
            />
          ) : (
            <AdminGrid>
              <AdminSection title={t("media:insights.activity")} icon="chart" span="full">
                <Timeline data={data} />
              </AdminSection>
              <AdminSection title={t("media:insights.top")} icon="trophy" span="full" flush>
                <TopWorks data={data} />
              </AdminSection>
              <AdminSection title={t("media:insights.when")} icon="clock">
                <Heatmap data={data} />
              </AdminSection>
              <AdminSection title={t("media:insights.byKind")} icon="list">
                <Bars
                  rows={data.by_kind.map((k) => ({
                    key: k.kind,
                    label: t(`media:insights.kind.${k.kind}`),
                    amount: k.seconds,
                    hint: t("media:insights.plays", { count: k.plays }),
                  }))}
                  value={measures.duration}
                />
              </AdminSection>
              {data.genres.length ? (
                <AdminSection title={t("media:insights.genres")} icon="palette">
                  <Bars rows={ranked(data.genres, t)} value={measures.hours} />
                </AdminSection>
              ) : null}
              {data.people.length ? (
                <AdminSection title={t("media:insights.people")} icon="user">
                  <Bars rows={ranked(data.people, t)} value={measures.hours} />
                </AdminSection>
              ) : null}
              {data.decades.length ? (
                <AdminSection title={t("media:insights.decades")} icon="calendar">
                  <Bars
                    rows={data.decades.map((d) => ({
                      key: String(d.decade),
                      label: t("media:insights.decade", { decade: d.decade }),
                      amount: d.seconds,
                      hint: t("media:insights.plays", { count: d.plays }),
                    }))}
                    value={measures.hours}
                  />
                </AdminSection>
              ) : null}
              <AdminSection title={t("media:insights.records.title")} icon="star">
                <Records data={data} />
              </AdminSection>
              {data.box_office ? (
                <AdminSection
                  title={t("media:insights.box.title")}
                  description={t("media:insights.box.hint")}
                  icon="coins"
                >
                  <BoxOffice data={data.box_office} />
                </AdminSection>
              ) : null}
              {data.requests?.total ? (
                <AdminSection title={t("media:insights.requests")} icon="inbox">
                  <Bars
                    rows={Object.entries(data.requests.states).map(([state, count]) => ({
                      key: state,
                      label: t(`media:requests.state.${state}`),
                      amount: count,
                    }))}
                    value={format.number}
                  />
                </AdminSection>
              ) : null}
              {data.platforms?.length ? (
                <AdminSection title={t("media:insights.platforms")} icon="gauge">
                  <Bars
                    rows={data.platforms.map((p) => ({
                      key: p.name,
                      label: p.name,
                      amount: p.plays,
                      hint: measures.duration(p.seconds),
                    }))}
                    value={(n) => t("media:insights.plays", { count: n })}
                  />
                </AdminSection>
              ) : null}
              {data.members?.length ? (
                <AdminSection title={t("media:insights.members")} icon="users" flush span="full">
                  <AdminTable
                    label={t("media:insights.members")}
                    rows={data.members}
                    rowKey={(m) => m.user_id ?? "unknown"}
                    columns={[
                      {
                        key: "who",
                        header: t("media:insights.member"),
                        primary: true,
                        render: (m) => <strong>{m.name ?? t("media:insights.unknownMember")}</strong>,
                      },
                      {
                        key: "time",
                        header: t("media:insights.stat.time"),
                        render: (m) => measures.duration(m.seconds),
                      },
                      {
                        key: "plays",
                        header: t("media:insights.stat.plays"),
                        render: (m) => format.number(m.plays),
                      },
                      {
                        key: "days",
                        header: t("media:insights.stat.days"),
                        render: (m) => format.number(m.active_days),
                      },
                      {
                        key: "last",
                        header: t("media:insights.lastDay"),
                        render: (m) => format.date(m.last_day),
                      },
                    ]}
                  />
                </AdminSection>
              ) : null}
              {data.recent?.length ? (
                <AdminSection title={t("media:insights.recent")} icon="activity" flush span="full">
                  <ul className="admin-list">
                    {data.recent.map((r) => (
                      <li key={`${r.at}-${r.title}`}>
                        <span className="admin-list__main">
                          <strong>
                            {r.work_id ? (
                              <Link to={`/media/${r.work_id}`}>{r.parent_title ?? r.title}</Link>
                            ) : (
                              (r.parent_title ?? r.title)
                            )}
                          </strong>
                          <span className="admin-muted">
                            {r.parent_title ? `${r.title} · ` : ""}
                            {t(`media:insights.kind.${r.kind}`)} · {format.dateTime(r.at)} ·{" "}
                            {measures.duration(r.seconds)}
                            {r.member ? ` · ${r.member}` : ""}
                            {r.platform ? ` · ${r.platform}` : ""}
                          </span>
                        </span>
                        {r.progress !== null ? (
                          <span className="admin-muted">{format.percent(r.progress)}</span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </AdminSection>
              ) : null}
            </AdminGrid>
          )}
        </>
      ) : null}
    </AdminPage>
  );
}
