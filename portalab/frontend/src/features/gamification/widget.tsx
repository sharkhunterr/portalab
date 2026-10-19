import { Link } from "react-router";
import { levelProgress } from "../../design-system/components/Badges";
import { Icon } from "../../design-system/components/Icon";
import { CurrencyShort } from "../../design-system/site/SiteLook";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { useActiveCampaigns } from "../campaigns/api";
import { registerWidgetComponent, type WidgetProps } from "../dashboard/widgets/registry";
import { toQuestItem, useProgression } from "./api";
import { BoostTag, GainsNow, useMyStreak } from "./boost";

export { useMyStreak };

import type { QuestItem } from "./quests/QuestList";
import "./gamification.css";

const VALUE_ICON: Record<string, string> = { xp: "sparkles", coins: "coins", contribution: "heart" };

const factor = (value: number) => `×${Number(value.toFixed(2))}`;

/** 027: what multiplies my gains right now — my play streak (with its multiplier), the boost bought in the
 * shop (#55), the campaigns running for me (what they boost), and the streak freezes I own (#54); nothing
 * when none is on. */
export function ProgressBoosts() {
  const t = useT();
  const streak = useMyStreak().data;
  const boost = useProgression().data?.boost;
  const active = useActiveCampaigns().data;
  const campaigns = (Array.isArray(active) ? active : []).filter((c) => (c.boosts ?? []).length);
  const streaking = streak?.enabled && streak.days > 0;
  const freezes = streak?.enabled ? (streak.freezes ?? 0) : 0;
  if (!streaking && !campaigns.length && !boost && !freezes) return null;
  return (
    <ul className="widget-level__boosts" aria-label={t("gamification:widget.progress.boosts")}>
      {boost ? (
        <li data-boost="boost">
          <BoostTag boost={boost} />
        </li>
      ) : null}
      {streaking && streak ? (
        <li data-boost="streak" title={t("gamification:widget.progress.streak", { days: streak.days })}>
          <Icon name="flame" size={13} />
          {t("gamification:widget.progress.streak", { days: streak.days })}
          {streak.multiplier > 1 ? <strong>{factor(streak.multiplier)}</strong> : null}
        </li>
      ) : null}
      {freezes ? (
        <li data-boost="freeze" title={t("gamification:freeze.owned", { count: freezes })}>
          <span>
            <Icon name="snowflake" size={13} />
            {t("gamification:freeze.owned", { count: freezes })}
          </span>
        </li>
      ) : null}
      {campaigns.map((campaign) => (
        <li key={campaign.key} data-boost="campaign" title={campaign.name}>
          <Link to={`/campaigns/${campaign.key}`}>
            <Icon name="star" size={13} />
            <span>{campaign.name}</span>
            {(campaign.boosts ?? []).map((boost) => (
              <strong key={boost.value}>
                {factor(boost.factor)} {t(`gamification:value.${boost.value}`)}
              </strong>
            ))}
          </Link>
        </li>
      ))}
    </ul>
  );
}

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

/** 027: a single row — the level, the bar to the next one, the XP still to earn, and the streak. */
function ProgressCompact({ payload }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const data = (payload.data ?? {}) as { level?: number };
  const progression = useProgression().data;
  const streak = useMyStreak().data;
  const level = progression?.level ?? data.level ?? 1;
  const next = progression?.next_level_at ?? null;
  const ratio = progression ? levelProgress(progression.xp, progression.level_floor, next) : 0;
  return (
    <Link
      to="/progression"
      className="widget-level widget-level--compact"
      style={{ "--ratio": ratio } as React.CSSProperties}
    >
      <span className="widget-level__badge" title={t("gamification:level", { level })}>
        <Icon name="trophy" size={13} />
        {format.number(level)}
      </span>
      <span
        className="widget-level__bar"
        role="progressbar"
        aria-label={t("gamification:level", { level })}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(ratio * 100)}
      >
        <span />
      </span>
      {progression && next !== null ? (
        <small className="widget-level__next">
          {format.compact(progression.xp - progression.level_floor)} /{" "}
          {format.compact(next - progression.level_floor)}
        </small>
      ) : null}
      {streak?.enabled && streak.days > 0 ? (
        <span
          className="widget-level__streak"
          title={t("gamification:widget.progress.streak", { days: streak.days })}
        >
          <Icon name="flame" size={13} />
          {format.number(streak.days)}
        </span>
      ) : null}
      {progression?.boost ? (
        <span className="widget-level__streak" data-boost="boost">
          <Icon name="rocket" size={13} />×{Number(progression.boost.factor.toFixed(2))}
        </span>
      ) : null}
    </Link>
  );
}

/** The classic look: the level and values, then what boosts my gains now (outside the link). */
function ProgressWithBoosts(props: WidgetProps) {
  if (props.compact) return <ProgressCompact {...props} />;
  return (
    <div className="widget-level-box">
      <ProgressWidget {...props} />
      <ProgressBoosts />
    </div>
  );
}

registerWidgetComponent("gamification.progress", ProgressWithBoosts);

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

function progressOf(quest: QuestItem): { current: number; target: number; ratio: number } {
  const current = quest.steps.reduce((sum, s) => sum + Math.min(s.current, s.target), 0);
  const target = quest.steps.reduce((sum, s) => sum + s.target, 0) || 1;
  return { current, target, ratio: quest.completed ? 1 : Math.min(1, current / target) };
}

/** 027: the ones still to do first, the closest to done at the top; the done ones after. */
export function byCloseness(quests: QuestItem[]): QuestItem[] {
  return [...quests].sort(
    (a, b) =>
      Number(a.completed) - Number(b.completed) ||
      (a.completed ? 0 : progressOf(b).ratio - progressOf(a).ratio),
  );
}

function Objective({ quest }: { quest: QuestItem }) {
  const t = useT();
  const format = useFormat();
  const { current, target, ratio } = progressOf(quest);
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
function DailyObjectivesWidget({ payload, compact }: WidgetProps) {
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
  const percent = quests.length ? Math.round((done / quests.length) * 100) : 0;
  if (compact)
    // 027: a single row — the overall bar only (count, bar, coins)
    return (
      <Link
        to="/progression"
        className="daily-objectives daily-objectives--compact"
        data-done={all || undefined}
      >
        <span className="daily-objectives__count">
          <Icon name={all ? "trophy" : "target"} size={16} />
          {format.number(done)}/{format.number(quests.length)}
        </span>
        <GainsNow mini />
        <span
          className="daily-objectives__track"
          role="progressbar"
          aria-label={t("gamification:daily.done", { done, count: quests.length })}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
        >
          <span style={{ inlineSize: `${percent}%` }} />
        </span>
        <span className="daily-reward" data-value="coins">
          <Icon name="coins" size={13} />
          {format.number(coins(quests.filter((q) => q.completed)))} / {format.number(coins(quests))}
          <CurrencyShort />
        </span>
      </Link>
    );
  return (
    <div className="daily-objectives" data-done={all || undefined}>
      <p className="daily-objectives__head">
        <span className="daily-objectives__count">
          <Icon name={all ? "trophy" : "target"} size={16} />
          {t("gamification:daily.done", { done, count: quests.length })}
        </span>
        <GainsNow />
        <span className="daily-reward" data-value="coins">
          <Icon name="coins" size={13} />
          {format.number(coins(quests.filter((q) => q.completed)))} / {format.number(coins(quests))}
          <CurrencyShort />
        </span>
      </p>
      <span className="daily-objectives__track" aria-hidden="true">
        <span style={{ inlineSize: `${percent}%` }} />
      </span>
      <ul className="daily-objectives__list">
        {byCloseness(quests).map((quest) => (
          <Objective key={quest.key} quest={quest} />
        ))}
      </ul>
    </div>
  );
}

registerWidgetComponent("gamification.daily_objectives", DailyObjectivesWidget);
