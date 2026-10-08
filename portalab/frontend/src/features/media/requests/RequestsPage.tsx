import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import {
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AdminEmpty,
  AdminGrid,
  AdminPage,
  AdminSection,
  AdminStats,
  AdminTabs,
  SearchBox,
  StatusBadge,
  type Tone,
} from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { SelectField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useRequestActions } from "../api";
import { useMeasures } from "../insights/api";
import {
  GROUP_OF,
  type RequestCard,
  type RequestInsights,
  useRequestInsights,
  useRequestList,
  useSoon,
} from "./api";
import "../../admin/admin.css";
import "../media.css";
import "./requests.css";
import { AcquisitionView } from "./Acquisition";
import { Poster, SoonList } from "./SoonList";

/**
 * My requests (027 — after Telemetra's « Demandes » tab). Overview: the funnel of my requests (ring), how many
 * I actually watched, films vs series, my rank among requesters (anonymous), requests over time against the
 * previous period, the community's most watched requested titles, the genres I request against the genres I
 * watch. List: every request with its poster, state and dates (cancel while pending). Coming soon: what is
 * downloading or importing (with progress), and what has a release date.
 */
const TABS = ["overview", "list", "soon"] as const;
const PERIODS = ["30d", "90d", "365d", "all"] as const;
const GROUPS = ["available", "approved", "pending", "declined"] as const;
const TONE: Record<string, Tone> = { available: "ok", approved: "info", pending: "warn", declined: "bad" };

function Funnel({ data }: { data: RequestInsights }) {
  const t = useT();
  const format = useFormat();
  const rows = GROUPS.map((g) => ({
    key: g,
    name: t(`media:myRequests.group.${g}`),
    value: data.summary[g],
  })).filter((r) => r.value > 0);
  return (
    <div className="requests-funnel">
      <div className="requests-funnel__ring">
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie
              data={rows}
              dataKey="value"
              nameKey="name"
              innerRadius="62%"
              outerRadius="95%"
              isAnimationActive={false}
            >
              {rows.map((row) => (
                <Cell key={row.key} fill={`var(--req-${row.key})`} stroke="var(--color-surface)" />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "var(--color-surface-raised)",
                border: "1px solid var(--color-border)",
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        <span className="requests-funnel__center">
          <strong>{format.number(data.summary.total)}</strong>
          <span>{t("media:myRequests.requests", { count: data.summary.total })}</span>
        </span>
      </div>
      <ul className="requests-funnel__legend">
        {GROUPS.map((g) => (
          <li key={g} data-group={g}>
            <span className="requests-swatch" />
            {t(`media:myRequests.group.${g}`)}
            <strong>{format.number(data.summary[g])}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Watched({ data }: { data: RequestInsights }) {
  const t = useT();
  const format = useFormat();
  const rate = data.watched.rate ?? 0;
  const total = data.by_kind.movie + data.by_kind.series || 1;
  return (
    <div className="requests-cards">
      <div className="requests-card">
        <span className="requests-card__label">{t("media:myRequests.watched")}</span>
        <span className="requests-card__value" data-tone="ok">
          {format.percent(rate)}
        </span>
        <span className="admin-muted">
          {t("media:myRequests.watchedOf", { watched: data.watched.watched, count: data.watched.requested })}
        </span>
        <span className="requests-meter">
          <span style={{ inlineSize: `${Math.round(rate * 100)}%` }} />
        </span>
      </div>
      <div className="requests-card">
        <span className="requests-card__label">{t("media:myRequests.split")}</span>
        <span className="requests-split" aria-hidden="true">
          <span data-kind="movie" style={{ inlineSize: `${(data.by_kind.movie / total) * 100}%` }} />
          <span data-kind="series" style={{ inlineSize: `${(data.by_kind.series / total) * 100}%` }} />
        </span>
        <span className="requests-split__legend">
          <span data-kind="movie">
            {t("media:insights.categories.movies")} {format.number(data.by_kind.movie)}
          </span>
          <span data-kind="series">
            {t("media:insights.categories.series")} {format.number(data.by_kind.series)}
          </span>
        </span>
      </div>
    </div>
  );
}

function Rank({ data }: { data: RequestInsights }) {
  const t = useT();
  const { position, total, count, delta } = data.ranking;
  return (
    <div className="requests-rank">
      <p className="requests-rank__position">
        <strong>{position ?? "—"}</strong>
        <span>/{total}</span>
      </p>
      <div className="requests-rank__text">
        <p>
          {position
            ? t("media:myRequests.rankText", { position, total })
            : t("media:myRequests.rankNone", { total })}
        </p>
        <p className="requests-rank__figures">
          <span>
            <span className="admin-muted">{t("media:myRequests.yourRequests")}</span>
            <strong>{count}</strong>
          </span>
          <span data-trend={delta === null ? undefined : delta > 0 ? "up" : delta < 0 ? "down" : "flat"}>
            <span className="admin-muted">{t("media:myRequests.vsPrevious")}</span>
            <strong>
              {delta === null ? "—" : delta > 0 ? `▲ +${delta}` : delta < 0 ? `▼ ${delta}` : "= 0"}
            </strong>
          </span>
        </p>
      </div>
    </div>
  );
}

function OverTime({ data }: { data: RequestInsights }) {
  const t = useT();
  const format = useFormat();
  if (!data.timeline.points.some((p) => p.count || p.previous)) {
    return <AdminEmpty icon="chart" title={t("media:insights.none")} />;
  }
  const label = (iso: string) =>
    data.timeline.unit === "month"
      ? new Date(iso).toLocaleDateString(undefined, { month: "short", year: "2-digit" })
      : format.date(iso, "short");
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data.timeline.points} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={label}
          stroke="var(--color-text-muted)"
          fontSize={12}
          minTickGap={24}
        />
        <YAxis allowDecimals={false} stroke="var(--color-text-muted)" fontSize={12} />
        <Tooltip
          labelFormatter={(v) => label(String(v))}
          contentStyle={{
            background: "var(--color-surface-raised)",
            border: "1px solid var(--color-border)",
          }}
        />
        <Line
          type="monotone"
          dataKey="previous"
          name={t("media:myRequests.previous")}
          stroke="var(--color-text-muted)"
          strokeDasharray="4 4"
          dot={false}
          isAnimationActive={false}
        />
        <Line
          type="monotone"
          dataKey="count"
          name={t("media:myRequests.current")}
          stroke="var(--color-accent)"
          strokeWidth={2.5}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function Genres({ data }: { data: RequestInsights }) {
  const t = useT();
  const requested = new Map(data.genres.requested.map((g) => [g.name, g.value]));
  const watched = new Map(data.genres.watched.map((g) => [g.name, g.value]));
  const names = [...new Set([...requested.keys(), ...watched.keys()])].slice(0, 8);
  if (names.length < 3) return <AdminEmpty icon="palette" title={t("media:myRequests.genresFew")} />;
  const rmax = Math.max(1, ...requested.values());
  const wmax = Math.max(1, ...watched.values());
  const rows = names.map((n) => ({
    genre: n,
    requested: Math.round(((requested.get(n) ?? 0) / rmax) * 100),
    watched: Math.round(((watched.get(n) ?? 0) / wmax) * 100),
  }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <RadarChart data={rows} outerRadius="72%">
        <PolarGrid stroke="var(--color-border)" />
        <PolarAngleAxis dataKey="genre" tick={{ fill: "var(--color-text-muted)", fontSize: 12 }} />
        <Radar
          name={t("media:myRequests.requested")}
          dataKey="requested"
          stroke="var(--color-accent)"
          fill="var(--color-accent)"
          fillOpacity={0.3}
          isAnimationActive={false}
        />
        <Radar
          name={t("media:myRequests.watchedGenres")}
          dataKey="watched"
          stroke="var(--color-accent-alt)"
          fill="var(--color-accent-alt)"
          fillOpacity={0.2}
          isAnimationActive={false}
        />
        <Tooltip
          contentStyle={{
            background: "var(--color-surface-raised)",
            border: "1px solid var(--color-border)",
          }}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}

export function Overview({ data }: { data: RequestInsights }) {
  const t = useT();
  const measures = useMeasures();
  if (!data.summary.total) {
    return (
      <AdminEmpty
        icon="inbox"
        title={t("media:myRequests.empty")}
        action={<Link to="/media/browse">{t("media:home.browse")}</Link>}
      />
    );
  }
  return (
    <AdminGrid>
      <AdminSection title={t("media:myRequests.status")} icon="target">
        <Funnel data={data} />
      </AdminSection>
      <AdminSection title={t("media:myRequests.whatBecame")} icon="check">
        <Watched data={data} />
      </AdminSection>
      <AdminSection
        title={t("media:myRequests.rank")}
        description={t("media:myRequests.rankHint")}
        icon="trophy"
        span="full"
      >
        <Rank data={data} />
      </AdminSection>
      <AdminSection
        title={t("media:myRequests.overTime")}
        description={t("media:myRequests.overTimeHint")}
        icon="chart"
        span="full"
      >
        <OverTime data={data} />
      </AdminSection>
      {data.acquisition ? (
        <AdminSection
          title={t("media:myRequests.acquisition")}
          description={t("media:myRequests.acquisitionHint")}
          icon="clock"
          span="full"
        >
          <AcquisitionView data={data.acquisition} />
        </AdminSection>
      ) : null}
      <AdminSection
        title={t("media:myRequests.topWatched")}
        description={t("media:myRequests.topWatchedHint")}
        icon="star"
        span="full"
        flush
      >
        {data.top_watched.length ? (
          <ol className="insights-posters">
            {data.top_watched.map((work, index) => (
              <li key={work.id} className="insights-poster">
                <Link to={work.route ?? `/media/${work.id}`}>
                  <span className="insights-poster__art">
                    {work.image_id ? (
                      <img src={`/api/v1/media/images/${work.image_id}`} alt="" loading="lazy" />
                    ) : (
                      <Icon name="film" size={28} />
                    )}
                    <span className="insights-poster__rank">{index + 1}</span>
                  </span>
                  <span className="insights-poster__title">{work.title}</span>
                  <span className="insights-poster__meta">
                    {t("media:insights.plays", { count: work.plays })} · {measures.duration(work.seconds)}
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        ) : (
          <AdminEmpty icon="star" title={t("media:insights.none")} />
        )}
      </AdminSection>
      <AdminSection
        title={t("media:myRequests.genres")}
        description={t("media:myRequests.genresHint")}
        icon="palette"
        span="full"
      >
        <Genres data={data} />
      </AdminSection>
    </AdminGrid>
  );
}

// 027: the request's stage, in the words of the title's journey
const STAGE_TONE: Record<string, "ok" | "info" | "warn" | "bad" | "neutral"> = {
  available: "ok",
  downloading: "info",
  importing: "info",
  import_blocked: "warn",
  awaiting_release: "neutral",
  searching: "neutral",
  pending: "neutral",
  declined: "bad",
  failed: "bad",
  cancelled: "neutral",
};

function RequestRow({ card }: { card: RequestCard }) {
  const t = useT();
  const format = useFormat();
  const { cancel } = useRequestActions();
  const group = GROUP_OF[card.state] ?? "pending";
  const body = (
    <>
      <Poster card={card} size="sm" />
      <span className="requests-row__main">
        <strong>{card.title}</strong>
        <span className="admin-muted">
          {t(`media:kind.${card.kind}`)} ·{" "}
          {t("media:myRequests.requestedOn", { date: format.date(card.requested_at) })}
          {card.state === "available" && card.updated_at
            ? ` · ${t("media:myRequests.availableOn", { date: format.date(card.updated_at) })}`
            : ""}
        </span>
      </span>
    </>
  );
  return (
    <li className="requests-row">
      {card.route ? <Link to={card.route}>{body}</Link> : <span className="requests-row__link">{body}</span>}
      <StatusBadge tone={STAGE_TONE[card.stage ?? ""] ?? TONE[group] ?? "neutral"}>
        {card.stage
          ? t(`media:myRequests.stage.${card.stage}`, {
              percent: Math.round((card.progress ?? 0) * 100),
              date: card.at ? format.date(card.at.slice(0, 10), "medium") : "",
            })
          : t(`media:requests.state.${card.state}`)}
      </StatusBadge>
      {card.state === "pending" ? (
        <Button variant="ghost" onClick={() => cancel.mutate(card.request_id)}>
          {t("media:requests.cancel")}
          <span className="visually-hidden">: {card.title}</span>
        </Button>
      ) : null}
    </li>
  );
}

function List() {
  const t = useT();
  const list = useRequestList();
  const [group, setGroup] = useState("all");
  const [query, setQuery] = useState("");
  if (list.isPending) return <FunctionalState state="loading" />;
  if (list.isError) return <FunctionalState state="error" onRetry={() => list.refetch()} />;
  const all = list.data ?? [];
  const count = (g: string) => all.filter((r) => GROUP_OF[r.state] === g).length;
  const needle = query.trim().toLowerCase();
  const shown = all.filter(
    (r) =>
      (group === "all" || GROUP_OF[r.state] === group) && (!needle || r.title.toLowerCase().includes(needle)),
  );
  return (
    <AdminSection title={t("media:myRequests.list")} icon="list" flush>
      <div className="config-toolbar">
        <SearchBox label={t("media:myRequests.search")} value={query} onChange={setQuery} />
        <AdminTabs
          label={t("media:myRequests.list")}
          current={group}
          onChange={setGroup}
          tabs={[
            { key: "all", label: t("media:insights.categories.all"), count: all.length },
            ...GROUPS.map((g) => ({ key: g, label: t(`media:myRequests.group.${g}`), count: count(g) })),
          ]}
        />
      </div>
      {shown.length ? (
        <ul className="requests-rows">
          {shown.map((card) => (
            <RequestRow key={card.request_id} card={card} />
          ))}
        </ul>
      ) : (
        <AdminEmpty icon="inbox" title={t("media:myRequests.noneMatch")} />
      )}
    </AdminSection>
  );
}

function Soon() {
  const t = useT();
  const soon = useSoon();
  if (soon.isPending) return <FunctionalState state="loading" />;
  if (soon.isError) return <FunctionalState state="error" onRetry={() => soon.refetch()} />;
  return (
    <AdminSection
      title={t("media:myRequests.soonTitle")}
      description={t("media:myRequests.soonHint")}
      icon="clock"
    >
      {soon.data?.length ? (
        <SoonList items={soon.data} />
      ) : (
        <AdminEmpty icon="clock" title={t("media:myRequests.soonNone")} />
      )}
    </AdminSection>
  );
}

export function RequestsPage() {
  const t = useT();
  const format = useFormat();
  const [params, setParams] = useSearchParams();
  const tab = (TABS as readonly string[]).includes(params.get("tab") ?? "")
    ? (params.get("tab") as string)
    : "overview";
  const [period, setPeriod] = useState("365d");
  const insights = useRequestInsights(period);
  const data = insights.data;
  const quota = data?.quota;
  return (
    <AdminPage
      icon="inbox"
      title={t("media:requests.title")}
      description={t("media:myRequests.subtitle")}
      primary={
        <Link className="ds-button ds-button--primary" to="/media/browse">
          <Icon name="plus" size={16} />
          {t("media:myRequests.new")}
        </Link>
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
        </SelectField>
      }
      tabs={
        <AdminTabs
          label={t("media:requests.title")}
          current={tab}
          onChange={(next) => setParams(next === "overview" ? {} : { tab: next }, { replace: true })}
          tabs={TABS.map((key) => ({ key, label: t(`media:myRequests.tabs.${key}`) }))}
        />
      }
    >
      {data ? (
        <AdminStats
          label={t("media:requests.title")}
          stats={[
            {
              key: "total",
              label: t("media:myRequests.stat.total"),
              value: format.number(data.summary.total),
              icon: "inbox",
              tone: "info",
              hint:
                data.previous_total !== null
                  ? t("media:myRequests.previousCount", { count: data.previous_total })
                  : undefined,
            },
            {
              key: "available",
              label: t("media:myRequests.group.available"),
              value: format.number(data.summary.available),
              icon: "check",
              tone: "ok",
            },
            {
              key: "approved",
              label: t("media:myRequests.group.approved"),
              value: format.number(data.summary.approved),
              icon: "arrow-down",
              tone: "info",
            },
            {
              key: "quota",
              label: t("media:myRequests.stat.quota"),
              value: format.number(Number(quota?.base_remaining ?? 0)),
              hint: t("media:requests.extra", { count: Number(quota?.extra_units ?? 0) }),
              icon: "coins",
              tone: "neutral",
            },
          ]}
        />
      ) : null}
      {insights.isPending ? <FunctionalState state="loading" /> : null}
      {insights.isError ? <FunctionalState state="error" onRetry={() => insights.refetch()} /> : null}
      {tab === "overview" && data ? <Overview data={data} /> : null}
      {tab === "list" ? <List /> : null}
      {tab === "soon" ? <Soon /> : null}
    </AdminPage>
  );
}

export default RequestsPage;
