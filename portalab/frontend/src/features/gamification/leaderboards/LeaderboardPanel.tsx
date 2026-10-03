import { useState } from "react";
import { SelectField } from "../../../design-system/components/Field";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useLeaderboard } from "../api";
import { LEADERBOARD_PERIODS, Leaderboard, type LeaderboardPeriod } from "./Leaderboard";

/** XP leaderboard on ``/progression`` (spec 013 T037): the viewer's own rank, period selector. */
export function LeaderboardPanel() {
  const t = useT();
  const [period, setPeriod] = useState<LeaderboardPeriod>("all");
  const board = useLeaderboard("xp", period);
  const caption = t("gamification:leaderboard.title");
  return (
    <section aria-labelledby="gamification-leaderboard" className="ds-card ds-stack">
      <h2 id="gamification-leaderboard">{caption}</h2>
      <SelectField
        label={t("gamification:leaderboard.period")}
        value={period}
        onChange={(e) => setPeriod(e.target.value as LeaderboardPeriod)}
      >
        {LEADERBOARD_PERIODS.map((value) => (
          <option key={value} value={value}>
            {t(`gamification:leaderboard.period.${value}`)}
          </option>
        ))}
      </SelectField>
      {board.isError ? <FunctionalState state="unavailable" onRetry={() => board.refetch()} /> : null}
      {board.data ? <Leaderboard caption={caption} rows={board.data.entries} me={board.data.me} /> : null}
    </section>
  );
}
