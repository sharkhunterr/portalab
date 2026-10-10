import { Link } from "react-router";
import { Avatar } from "../../../design-system/components/Avatar";
import { Icon } from "../../../design-system/components/Icon";
import { type Column, Table } from "../../../design-system/components/Layout";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import "../gamification.css";

/** One ranked member as both the 013 and the 012 APIs return it. */
export interface RankRow {
  rank: number;
  user_id: string;
  display_name: string | null;
  score: number;
  me: boolean;
  /** #66: places gained (> 0) or lost (< 0) since a day; absent: no reference */
  change?: number | null;
  new?: boolean;
  /** #66: a member keeping their progression private — no name, avatar nor profile */
  anonymous?: boolean;
}

/** #66: places gained, lost or kept since a day — an arrow and the count, said in words for everyone. */
export function RankMove({ row }: { row: RankRow }) {
  const t = useT();
  if (row.new) {
    return (
      <span className="rank-move" data-move="new">
        {t("gamification:leaderboard.new")}
      </span>
    );
  }
  if (row.change === undefined || row.change === null) return null;
  const move = row.change > 0 ? "up" : row.change < 0 ? "down" : "same";
  const count = Math.abs(row.change);
  const label = t(`gamification:leaderboard.move.${move}`, { count });
  return (
    <span className="rank-move" data-move={move} title={label}>
      <Icon name={move === "up" ? "arrow-up" : move === "down" ? "arrow-down" : "minus"} size={13} />
      {count ? <span aria-hidden="true">{count}</span> : null}
      <span className="visually-hidden">{label}</span>
    </span>
  );
}

/** #66: a member's face and name — or « Anonymous » for one keeping their progression private. */
export function RankWho({ row, link = false }: { row: RankRow; link?: boolean }) {
  const t = useT();
  if (row.anonymous) {
    return (
      <span className="rank-who" data-anonymous="true">
        <span className="rank-who__ghost" aria-hidden="true">
          <Icon name="user" size={14} />
        </span>
        <em>{t("gamification:leaderboard.anonymous")}</em>
      </span>
    );
  }
  const label = row.display_name ?? t("gamification:leaderboard.member");
  const text = row.me ? `${label} (${t("gamification:leaderboard.you")})` : label;
  return (
    <span className="rank-who">
      <Avatar
        name={label}
        userId={row.user_id}
        src={`/api/v1/users/${row.user_id}/avatar`}
        size="sm"
        decorative
      />
      {link && !row.me ? <Link to={`/community/members/${row.user_id}`}>{text}</Link> : <span>{text}</span>}
    </span>
  );
}

export const LEADERBOARD_PERIODS = ["all", "month", "week"] as const;
export type LeaderboardPeriod = (typeof LEADERBOARD_PERIODS)[number];

/**
 * Leaderboard table (spec 013 T037): an accessible table with the viewer's own row highlighted in text and
 * style (never color alone), and the viewer's own position stated below the table.
 */
export function Leaderboard({
  caption,
  rows,
  me,
  profileLinks = false,
}: {
  caption: string;
  rows: RankRow[];
  me: RankRow | null | undefined;
  profileLinks?: boolean;
}) {
  const t = useT();
  const format = useFormat();
  const columns: Column<RankRow>[] = [
    {
      key: "rank",
      header: t("gamification:leaderboard.rank"),
      render: (row) => `#${row.rank}`,
      rowHeader: true,
    },
    {
      key: "member",
      header: t("gamification:leaderboard.member"),
      render: (row) =>
        row.me ? (
          <strong>
            <RankWho row={row} link={profileLinks} />
          </strong>
        ) : (
          <RankWho row={row} link={profileLinks} />
        ),
    },
    { key: "score", header: t("gamification:leaderboard.score"), render: (row) => format.number(row.score) },
    {
      key: "move",
      header: t("gamification:leaderboard.moveHeader"),
      render: (row) => <RankMove row={row} />,
    },
  ];
  return (
    <div className="ds-stack leaderboard">
      {rows.length ? (
        <Table caption={caption} columns={columns} rows={rows} rowKey={(row) => row.user_id} />
      ) : (
        <p>{t("gamification:leaderboard.empty")}</p>
      )}
      <p className="leaderboard-me">
        {me
          ? t("gamification:leaderboard.myPosition", { rank: me.rank, score: format.number(me.score) })
          : t("gamification:leaderboard.notRanked")}
      </p>
    </div>
  );
}
