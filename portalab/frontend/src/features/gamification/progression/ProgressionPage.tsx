import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { AchievementGrid } from "../achievements/Grid";
import { useAchievements, useProgression } from "../api";
import { History } from "../history/History";
import { ProgressionCard } from "./ProgressionCard";
import "../gamification.css";

/** ``/progression`` (spec 013): my level and values, achievements and history. */
export default function ProgressionPage() {
  const t = useT();
  const progression = useProgression();
  const achievements = useAchievements();
  return (
    <div className="ds-stack">
      <h1>{t("gamification:progression.title")}</h1>
      {progression.isError ? <FunctionalState state="unavailable" /> : null}
      {progression.data ? <ProgressionCard progression={progression.data} /> : null}
      {achievements.data?.length ? <AchievementGrid achievements={achievements.data} /> : null}
      <History />
    </div>
  );
}
