import { useQuery } from "@tanstack/react-query";
import { api } from "../../../api/client";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { type QuestItem, QuestList } from "../../gamification/quests/QuestList";

/** Quest board (spec 012 T020): the viewer's own quests; challenges appear as time-boxed quests. */
export function QuestBoard() {
  const t = useT();
  const quests = useQuery({
    queryKey: ["community", "quests"],
    queryFn: async () => (await api.GET("/api/v1/community/quests")).data,
  });
  return (
    <section aria-labelledby="community-quests" className="ds-stack">
      <h2 id="community-quests">{t("community:quests.title")}</h2>
      {quests.isError || quests.data?.state === "unavailable" ? (
        <FunctionalState state="unavailable" label={t("community:progress.unavailable")} />
      ) : null}
      {quests.data && quests.data.state !== "unavailable" ? (
        <QuestList quests={quests.data.items as unknown as QuestItem[]} />
      ) : null}
    </section>
  );
}
