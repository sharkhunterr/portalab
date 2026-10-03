import { Link } from "react-router";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { registerWidgetComponent, type WidgetProps } from "../dashboard/widgets/registry";
import { toQuestItem } from "./api";
import { QuestList } from "./quests/QuestList";

/** Dashboard widget ``gamification.progress`` (spec 013 T030): level and the three values, separately. */
function ProgressWidget({ payload }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const data = (payload.data ?? {}) as { level?: number; xp?: number; contribution?: number; coins?: number };
  return (
    <div className="widget-progress">
      <p>
        <Link to="/progression">{t("gamification:level", { level: data.level ?? 1 })}</Link>
      </p>
      <ul className="widget-list">
        {(["xp", "contribution", "coins"] as const).map((value) => (
          <li key={value}>
            {t(`gamification:value.${value}`)}: {format.number(data[value] ?? 0)}
          </li>
        ))}
      </ul>
    </div>
  );
}

registerWidgetComponent("gamification.progress", ProgressWidget);

/** Dashboard widget ``gamification.daily_objectives`` (spec 013 T039): today's daily objectives. */
function DailyObjectivesWidget({ payload }: WidgetProps) {
  const items = ((payload.data ?? {}) as { items?: Parameters<typeof toQuestItem>[0][] }).items ?? [];
  return <QuestList quests={items.map(toQuestItem)} />;
}

registerWidgetComponent("gamification.daily_objectives", DailyObjectivesWidget);
