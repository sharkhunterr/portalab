import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { registerWidgetComponent, type WidgetProps } from "../dashboard/widgets/registry";
import { toQuestItem } from "./api";
import type { QuestItem } from "./quests/QuestList";
import "./gamification.css";

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

const REWARD_ICON: Record<string, string> = { coins: "coins", xp: "sparkles", contribution: "heart" };

function Reward({ value, amount }: { value: string; amount: number }) {
  const t = useT();
  const format = useFormat();
  return (
    <span className="daily-reward" data-value={value} title={t(`gamification:value.${value}`)}>
      <Icon name={REWARD_ICON[value] ?? "gift"} size={13} />+{format.number(amount)}
    </span>
  );
}

function Objective({ quest }: { quest: QuestItem }) {
  const t = useT();
  const format = useFormat();
  const current = quest.steps.reduce((sum, s) => sum + Math.min(s.current, s.target), 0);
  const target = quest.steps.reduce((sum, s) => sum + s.target, 0) || 1;
  const ratio = quest.completed ? 1 : Math.min(1, current / target);
  return (
    <li className="daily-objective" data-done={quest.completed || undefined}>
      <span className="daily-objective__check" aria-hidden="true">
        <Icon name={quest.completed ? "check" : "target"} size={16} />
      </span>
      <span className="daily-objective__body">
        <span className="daily-objective__label">{quest.label}</span>
        <span className="daily-objective__bar" aria-hidden="true">
          <span style={{ inlineSize: `${Math.round(ratio * 100)}%` }} />
        </span>
        <span className="daily-objective__count">
          {quest.completed
            ? t("gamification:quests.completed")
            : `${format.number(current)} / ${format.number(target)}`}
        </span>
      </span>
      <span className="daily-objective__rewards">
        {quest.rewards.map((r) => (
          <Reward key={r.value} value={r.value} amount={r.amount} />
        ))}
      </span>
    </li>
  );
}

/** Dashboard widget ``gamification.daily_objectives`` (spec 013 T039; 027 redesign): today's daily
 * objectives — the count done and the coins at stake on one line, each objective with its reward badge. */
function DailyObjectivesWidget({ payload }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const items = ((payload.data ?? {}) as { items?: Parameters<typeof toQuestItem>[0][] }).items ?? [];
  const quests = items.map(toQuestItem);
  const done = quests.filter((q) => q.completed).length;
  const coins = (list: QuestItem[]) =>
    list.reduce(
      (sum, q) => sum + q.rewards.filter((r) => r.value === "coins").reduce((a, r) => a + r.amount, 0),
      0,
    );
  const all = done === quests.length && quests.length > 0;
  return (
    <div className="daily-objectives" data-done={all || undefined}>
      <p className="daily-objectives__head">
        <span className="daily-objectives__count">
          <Icon name={all ? "trophy" : "target"} size={16} />
          {t("gamification:daily.done", { done, count: quests.length })}
        </span>
        <span className="daily-reward" data-value="coins">
          <Icon name="coins" size={13} />
          {format.number(coins(quests.filter((q) => q.completed)))} / {format.number(coins(quests))}
        </span>
      </p>
      <span className="daily-objectives__track" aria-hidden="true">
        <span style={{ inlineSize: `${quests.length ? Math.round((done / quests.length) * 100) : 0}%` }} />
      </span>
      <ul className="daily-objectives__list">
        {quests.map((quest) => (
          <Objective key={quest.key} quest={quest} />
        ))}
      </ul>
    </div>
  );
}

registerWidgetComponent("gamification.daily_objectives", DailyObjectivesWidget);
