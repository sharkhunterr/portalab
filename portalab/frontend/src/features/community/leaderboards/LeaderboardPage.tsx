import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import {
  LEADERBOARD_PERIODS,
  Leaderboard,
  RankMove,
  type RankRow,
  useLeaderboardPeriod,
} from "../../gamification/leaderboards/Leaderboard";
import { MemberAvatar, MemberName } from "../MemberFace";

/** Who stands on the podium: the first three entries placed 1 to 3 (issue 120: ex aequo share a place). */
const podiumOf = (rows: RankRow[]) => rows.filter((r) => r.rank <= 3).slice(0, 3);

/** The first three on steps (027): second, first, third — avatar, name and score. */
export function Podium({ rows }: { rows: RankRow[] }) {
  const t = useT();
  const format = useFormat();
  const top = podiumOf(rows);
  if (!top.length) return null;
  const order = [top[1], top[0], top[2]].filter((r): r is RankRow => Boolean(r));
  return (
    <ol className="community-podium" aria-label={t("community:leaderboards.podium")}>
      {order.map((row) => (
        <li key={row.user_id} data-rank={row.rank} data-me={row.me || undefined}>
          {row.anonymous ? (
            // #66: a member keeping their progression private: their place, without a face nor a name
            <span className="community-podium__who" data-anonymous="true">
              <span className="community-podium__medal" aria-hidden="true">
                <Icon name={row.rank === 1 ? "crown" : "medal"} size={16} />
              </span>
              <span
                className="community-podium__ghost"
                data-size={row.rank === 1 ? "xl" : "lg"}
                aria-hidden="true"
              >
                <Icon name="user" size={row.rank === 1 ? 36 : 28} />
              </span>
              <em>{t("gamification:leaderboard.anonymous")}</em>
              <span className="community-meta">{format.number(row.score)}</span>
              <RankMove row={row} />
            </span>
          ) : (
            <Link to={`/community/members/${row.user_id}`} className="community-podium__who">
              <span className="community-podium__medal" aria-hidden="true">
                <Icon name={row.rank === 1 ? "crown" : "medal"} size={16} />
              </span>
              <MemberAvatar
                id={row.user_id}
                name={row.display_name ?? ""}
                look={row.look}
                size={row.rank === 1 ? "xl" : "lg"}
              />
              <strong>
                <MemberName name={row.display_name ?? t("gamification:leaderboard.member")} look={row.look} />
              </strong>
              <span className="community-meta">{format.number(row.score)}</span>
              <RankMove row={row} />
            </Link>
          )}
          <span className="community-podium__step">#{row.rank}</span>
        </li>
      ))}
    </ol>
  );
}

/**
 * ``/community/leaderboards`` (spec 012 T018): 013's leaderboards as the viewer may see them — metric and
 * period selectors, own rank highlighted; ``unavailable`` when 013 is down, without breaking the page.
 */
export function LeaderboardPage() {
  const t = useT();
  const format = useFormat();
  const metrics = useQuery({
    queryKey: ["community", "leaderboards"],
    queryFn: async () => ((await api.GET("/api/v1/community/leaderboards")).data ?? []) as string[],
  });
  const [metric, setMetric] = useState("xp");
  const [period, setPeriod] = useLeaderboardPeriod();
  const available = metrics.data ?? [];
  const current = available.includes(metric) ? metric : (available[0] ?? metric);
  const effectivePeriod = current === "level" ? "all" : period;
  const board = useQuery({
    queryKey: ["community", "leaderboard", current, effectivePeriod],
    enabled: available.length > 0,
    queryFn: async () =>
      (
        await api.GET("/api/v1/community/leaderboards/{metric}", {
          params: { path: { metric: current }, query: { period: effectivePeriod } },
        })
      ).data,
  });
  const heading = t("community:leaderboards.title");
  return (
    <section aria-label={heading} className="ds-stack">
      {metrics.isSuccess && available.length === 0 ? (
        <FunctionalState state="unavailable" label={t("community:leaderboards.unavailable")} />
      ) : null}
      {available.length ? (
        <div className="community-filters">
          <fieldset className="ds-subnav" aria-label={t("community:leaderboards.metric")}>
            {available.map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={value === current}
                onClick={() => setMetric(value)}
              >
                {t(`community:leaderboards.metric.${value}`)}
              </button>
            ))}
          </fieldset>
          {current !== "level" ? (
            <fieldset className="ds-subnav" aria-label={t("community:leaderboards.period")}>
              {LEADERBOARD_PERIODS.map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={value === effectivePeriod}
                  onClick={() => setPeriod(value)}
                >
                  {t(`community:leaderboards.period.${value}`)}
                </button>
              ))}
            </fieldset>
          ) : null}
        </div>
      ) : null}
      {board.isError || board.data?.state === "unavailable" ? (
        <FunctionalState state="unavailable" label={t("community:leaderboards.unavailable")} />
      ) : null}
      {board.data && board.data.state !== "unavailable" ? (
        <>
          <Podium rows={board.data.entries} />
          <Leaderboard
            caption={`${heading} — ${t(`community:leaderboards.metric.${current}`)}`}
            // #66: the others, under the podium — every one of them, whatever place they share
            rows={board.data.entries.slice(podiumOf(board.data.entries).length)}
            me={board.data.me}
            profileLinks
          />
          {board.data.computed_at ? (
            <p className="community-meta">
              {t("community:leaderboards.asOf", { date: format.dateTime(board.data.computed_at) })}
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
