import { useQuery } from "@tanstack/react-query";
import { api } from "../../../api/client";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { AchievementGrid } from "../../gamification/achievements/Grid";
import type { AchievementView } from "../../gamification/api";

/** ``/community/achievements`` showcase (spec 012 T020): 013's achievements, hidden ones revealing nothing. */
export function Showcase() {
  const t = useT();
  const achievements = useQuery({
    queryKey: ["community", "achievements"],
    queryFn: async () => (await api.GET("/api/v1/community/achievements")).data,
  });
  if (achievements.isError || achievements.data?.state === "unavailable") {
    return <FunctionalState state="unavailable" label={t("community:progress.unavailable")} />;
  }
  if (!achievements.data) return null;
  return <AchievementGrid achievements={achievements.data.items as unknown as AchievementView[]} />;
}
