import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { WidgetHeaderAction, WidgetHeaderLink } from "../dashboard/frame/actions";
import { registerWidgetComponent, type WidgetProps } from "../dashboard/widgets/registry";
import {
  LEADERBOARD_PERIODS,
  type LeaderboardPeriod,
  RankMove,
  type RankRow,
  RankWho,
} from "../gamification/leaderboards/Leaderboard";
import { FEED_ICONS, FeedText } from "./feed/FeedText";
import { Podium } from "./leaderboards/LeaderboardPage";
import { MemberAvatar, type MemberLook } from "./MemberFace";
import "./community.css";

interface ActivityItem {
  id: string;
  kind?: string;
  actor_id: string;
  actor_name: string | null;
  anonymous?: boolean;
  look?: MemberLook | null;
  params: Record<string, unknown>;
  occurred_at?: string;
}

function Who({ item }: { item: ActivityItem }) {
  return (
    <span className="widget-activity__who">
      <MemberAvatar
        id={item.actor_id}
        name={item.actor_name ?? ""}
        look={item.look}
        anonymous={item.anonymous}
      />
      <span className="widget-activity__icon" aria-hidden="true">
        <Icon name={FEED_ICONS[item.kind ?? ""] ?? "activity"} size={10} />
      </span>
    </span>
  );
}

/**
 * Dashboard widget ``community.activity`` (spec 012 T015; 027 redesign): the latest entries the viewer may
 * see — who (avatar and what kind of thing), what, and when — as rows that fill the block, in two columns
 * on a wide one; on a single row, the latest only. The whole feed is one click away in the header.
 */
function ActivityWidget({ payload, compact }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const items = ((payload.data ?? {}) as { items?: ActivityItem[] }).items ?? [];
  const when = (item: ActivityItem) =>
    item.occurred_at ? format.relative((Date.parse(item.occurred_at) - Date.now()) / 1000) : null;
  const text = (item: ActivityItem) => (
    <FeedText
      kind={item.kind ?? ""}
      actorId={item.actor_id}
      actorName={item.actor_name}
      anonymous={item.anonymous}
      params={item.params}
      look={item.look}
    />
  );
  const latest = items[0];
  if (compact && latest)
    return (
      <div className="widget-activity widget-activity--compact" data-kind={latest.kind}>
        <Who item={latest} />
        <span className="widget-activity__text">{text(latest)}</span>
        <time dateTime={latest.occurred_at}>{when(latest)}</time>
      </div>
    );
  return (
    <>
      <WidgetHeaderAction>
        <Link
          to="/community/feed"
          className="widget-activity__all"
          aria-label={t("community:widget.activity.open")}
          title={t("community:widget.activity.open")}
        >
          <Icon name="chevron-right" size={14} />
        </Link>
      </WidgetHeaderAction>
      <ul className="widget-activity">
        {items.map((item) => (
          <li key={item.id} data-kind={item.kind}>
            <Who item={item} />
            <span className="widget-activity__text">{text(item)}</span>
            <time dateTime={item.occurred_at}>{when(item)}</time>
          </li>
        ))}
      </ul>
    </>
  );
}

registerWidgetComponent("community.activity", ActivityWidget);

interface ProjectItem {
  id: string;
  title: string;
  help_wanted: boolean;
  votes: number;
}

/** Dashboard widget ``community.projects`` (spec 012 T024, REQ-018): proposals open for votes or help. */
function ProjectsWidget({ payload }: WidgetProps) {
  const t = useT();
  const items = ((payload.data ?? {}) as { items?: ProjectItem[] }).items ?? [];
  return (
    <ul className="widget-list">
      {items.map((item) => (
        <li key={item.id}>
          <Link to={`/community/proposals/${item.id}`}>{item.title}</Link> ·{" "}
          {t("community:proposals.votes", { count: item.votes })}
          {item.help_wanted ? ` · ${t("community:proposals.helpWanted")}` : ""}
        </li>
      ))}
    </ul>
  );
}

registerWidgetComponent("community.projects", ProjectsWidget);

interface LeaderboardData {
  metric: string;
  period: string;
  entries: RankRow[];
  me: RankRow | null;
  total: number;
}

const BOARD_ROWS = 10;

/** The leaderboard of another period than the widget's own (its first ten, my place, how many ranked). */
function useOtherPeriod(metric: string, period: string, enabled: boolean) {
  return useQuery({
    queryKey: ["community", "leaderboard", metric, period, "widget"],
    enabled,
    staleTime: 60_000,
    queryFn: async (): Promise<LeaderboardData | null> => {
      const board = (
        await api.GET("/api/v1/community/leaderboards/{metric}", {
          params: { path: { metric }, query: { period: period as LeaderboardPeriod, limit: 100 } },
        })
      ).data;
      if (!board || board.state === "unavailable") return null;
      return {
        metric,
        period,
        entries: board.entries.slice(0, BOARD_ROWS) as RankRow[],
        me: (board.me as RankRow | null) ?? null,
        total: board.entries.length,
      };
    },
  });
}

/** The period, in a small menu (the leaderboards page's periods; « level » has only all time). */
function PeriodPicker({
  metric,
  value,
  onChange,
}: {
  metric: string;
  value: string;
  onChange: (p: string) => void;
}) {
  const t = useT();
  if (metric === "level") return null;
  return (
    <select
      className="widget-leaderboard__period"
      value={value}
      aria-label={t("community:widget.leaderboard.period")}
      onChange={(event) => onChange(event.target.value)}
    >
      {LEADERBOARD_PERIODS.map((p) => (
        <option key={p} value={p}>
          {t(`community:leaderboards.period.${p}`)}
        </option>
      ))}
    </select>
  );
}

/** « 3 / 8 » and the places gained since a day — or « not ranked yet ». */
function MyPlace({ data }: { data: LeaderboardData }) {
  const t = useT();
  const format = useFormat();
  if (!data.me)
    return <span className="widget-leaderboard__mine">{t("community:widget.leaderboard.unranked")}</span>;
  const rank = format.number(data.me.rank);
  const total = format.number(Math.max(data.total, data.me.rank));
  return (
    <span
      className="widget-leaderboard__mine"
      title={t("community:widget.leaderboard.rankLabel", { rank, total })}
    >
      <Icon name="trophy" size={14} />
      <strong>{t("community:widget.leaderboard.rank", { rank, total })}</strong>
      <span className="widget-leaderboard__score">{format.number(data.me.score)}</span>
      <RankMove row={data.me} />
    </span>
  );
}

/**
 * Dashboard widget ``community.leaderboard`` (issue 189): the leaderboards page in a block — the podium,
 * the ranking under it, my place apart when I am further down; its period changed in the widget (its
 * default in its settings). On a single row: my place (« 3 / 8 », places gained) and the period.
 */
function LeaderboardWidget({ payload, compact }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const own = (payload.data ?? null) as LeaderboardData | null;
  const metric = own?.metric ?? "xp";
  const [period, setPeriod] = useState(own?.period ?? "month");
  const other = useOtherPeriod(metric, period, Boolean(own) && period !== own?.period);
  const data = period === own?.period ? own : (other.data ?? (other.isPending ? own : null));
  const link = "/community/leaderboards";
  if (compact)
    return (
      <div className="widget-leaderboard-line">
        <Link to={link} className="widget-leaderboard-line__place">
          {data ? <MyPlace data={data} /> : null}
        </Link>
        <PeriodPicker metric={metric} value={period} onChange={setPeriod} />
      </div>
    );
  const rest = (data?.entries ?? []).filter((row) => row.rank > 3);
  const meApart = data?.me && !data.entries.some((row) => row.me) ? data.me : null;
  return (
    <>
      <WidgetHeaderAction>
        <PeriodPicker metric={metric} value={period} onChange={setPeriod} />
      </WidgetHeaderAction>
      <WidgetHeaderLink to={link} label={t("community:widget.leaderboard.all")} />
      {data ? (
        <div
          className="widget-leaderboard"
          data-loading={(other.isFetching && period !== own?.period) || undefined}
        >
          <div className="widget-leaderboard__podium" data-nofit>
            <Podium rows={data.entries} />
          </div>
          {rest.length ? (
            <ol className="widget-leaderboard__rows">
              {rest.map((row) => (
                <li key={row.user_id} data-me={row.me || undefined}>
                  <span className="widget-leaderboard__rank">{row.rank}</span>
                  <RankWho row={row} link={!row.anonymous} />
                  <span className="widget-leaderboard__score">{format.number(row.score)}</span>
                  <RankMove row={row} />
                </li>
              ))}
            </ol>
          ) : null}
          {meApart ? (
            <p className="widget-leaderboard__me">
              <MyPlace data={data} />
            </p>
          ) : null}
        </div>
      ) : (
        <p className="widget-empty" data-state="no-data">
          <Icon name="trophy" size={28} />
          <span>{t("community:widget.leaderboard.unranked")}</span>
        </p>
      )}
    </>
  );
}

registerWidgetComponent("community.leaderboard", LeaderboardWidget);
