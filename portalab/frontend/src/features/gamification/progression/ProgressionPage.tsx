import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { AchievementGrid } from "../achievements/Grid";
import { useAchievements, useProgression } from "../api";
import { History } from "../history/History";
import { LeaderboardPanel } from "../leaderboards/LeaderboardPanel";
import { QuestPanel } from "../quests/QuestPanel";
import { GainSources } from "./GainSources";
import { PlaysByKind } from "./PlaysByKind";
import { ProgressionCard } from "./ProgressionCard";
import { StreakCard } from "./StreakCard";
import "../gamification.css";
import { PageHeader } from "../../../design-system/components/PageHeader";

/** ``/progression`` (spec 013): my level and values, achievements and history. */
export default function ProgressionPage() {
  const t = useT();
  const progression = useProgression();
  const achievements = useAchievements();
  return (
    <div className="ds-stack">
      <PageHeader icon="trophy" title={t("gamification:progression.title")} />
      {progression.isError ? <FunctionalState state="unavailable" /> : null}
      {progression.data ? <ProgressionCard progression={progression.data} /> : null}
      <StreakCard />
      <GainSources />
      <PlaysByKind />
      {achievements.data?.length ? <AchievementGrid achievements={achievements.data} /> : null}
      <QuestPanel />
      <LeaderboardPanel />
      <History />
    </div>
  );
}
