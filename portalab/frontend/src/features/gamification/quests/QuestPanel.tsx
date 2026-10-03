import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useQuests } from "../api";
import { QuestList } from "./QuestList";

/** ``/progression`` quests panel (spec 013 T039): the viewer's open quests for the current period. */
export function QuestPanel() {
  const t = useT();
  const quests = useQuests();
  return (
    <section aria-labelledby="gamification-quests" className="ds-stack">
      <h2 id="gamification-quests">{t("gamification:quests.title")}</h2>
      {quests.isError ? <FunctionalState state="unavailable" onRetry={() => quests.refetch()} /> : null}
      {quests.data ? <QuestList quests={quests.data} /> : null}
    </section>
  );
}
