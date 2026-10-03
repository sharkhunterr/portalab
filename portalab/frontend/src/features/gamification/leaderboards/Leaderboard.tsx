import { Link } from "react-router";
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
  const name = (row: RankRow) => {
    const label = row.display_name ?? t("gamification:leaderboard.member");
    const text = row.me ? `${label} (${t("gamification:leaderboard.you")})` : label;
    return profileLinks && !row.me ? <Link to={`/community/members/${row.user_id}`}>{text}</Link> : text;
  };
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
      render: (row) => (row.me ? <strong>{name(row)}</strong> : name(row)),
    },
    { key: "score", header: t("gamification:leaderboard.score"), render: (row) => format.number(row.score) },
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
