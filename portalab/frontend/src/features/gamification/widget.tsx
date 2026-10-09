import { Link } from "react-router";
import { levelProgress } from "../../design-system/components/Badges";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { registerWidgetComponent, type WidgetProps } from "../dashboard/widgets/registry";
import { toQuestItem, useProgression } from "./api";
import type { QuestItem } from "./quests/QuestList";
import "./gamification.css";

const VALUE_ICON: Record<string, string> = { xp: "sparkles", coins: "coins", contribution: "heart" };

/** Dashboard widget ``gamification.progress`` (spec 013 T030; 027 #12): the level as a ring filled up to the
 * next one, the XP still to earn, and the three values as chips — all sized to the block. */
function ProgressWidget({ payload }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const data = (payload.data ?? {}) as { level?: number; xp?: number; contribution?: number; coins?: number };
  const progression = useProgression().data;
  const level = progression?.level ?? data.level ?? 1;
  const next = progression?.next_level_at ?? null;
  const ratio = progression ? levelProgress(progression.xp, progression.level_floor, next) : 0;
  return (
    <Link to="/progression" className="widget-level" style={{ "--ratio": ratio } as React.CSSProperties}>
      <span
        className="widget-level__ring"
        role="progressbar"
        aria-label={t("gamification:level", { level })}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(ratio * 100)}
      >
        <strong>{format.number(level)}</strong>
      </span>
      <span className="widget-level__side">
        <span className="widget-level__name">{t("gamification:level", { level })}</span>
        {progression && next !== null ? (
          <span className="widget-level__next">
            <span className="widget-level__bar" aria-hidden="true">
              <span />
            </span>
            <small>
              {format.number(progression.xp - progression.level_floor)} /{" "}
              {format.number(next - progression.level_floor)} XP
            </small>
          </span>
        ) : null}
        <ul className="widget-level__values">
          {(["xp", "coins", "contribution"] as const).map((value) => (
            <li key={value} data-value={value}>
              <Icon name={VALUE_ICON[value] ?? "star"} size={14} />
              <strong>{format.compact(data[value] ?? 0)}</strong>
              <span>{t(`gamification:value.${value}`)}</span>
            </li>
          ))}
        </ul>
      </span>
    </Link>
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
