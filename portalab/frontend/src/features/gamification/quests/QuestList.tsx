import { useEffect, useState } from "react";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import "../gamification.css";

/** A quest, daily objective or challenge as both the 013 and 012 APIs describe it. */
export interface QuestItem {
  key: string;
  kind: "quest" | "daily" | "challenge" | string;
  label: string;
  description?: string | null;
  icon?: string | null;
  period?: string | null;
  ends_at?: string | null;
  completed: boolean;
  steps: Array<{ current: number; target: number }>;
  rewards: Array<{ value: string; amount: number }>;
  /** 027: what it gives from the shop (a sealed booster…), by name. */
  gifts?: string[];
  /** issue 307: its texts in other interface languages. */
  translations?: Record<string, { label: string; description?: string }> | null;
  /** issue 307: when a daily, weekly or monthly objective starts again. */
  resets_at?: string | null;
  /** issue 121: done by any one of its steps (its guided tour or the thing itself). */
  complete_on?: "all" | "any" | string | null;
}

/** issue 307: a quest's label and description in the interface's language, else as written. */
export function useQuestText() {
  const { language } = useLocaleContext();
  return (quest: QuestItem) => {
    const text = quest.translations?.[language] ?? quest.translations?.[language.split("-")[0] ?? ""];
    return text
      ? { label: text.label, description: text.description ?? "" }
      : { label: quest.label, description: quest.description ?? "" };
  };
}

/** The time now, again each minute — so the countdowns move. */
function useNow(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);
  return now;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
/** Beyond a week, a date says it better than a count of days. */
const COUNTDOWN = 7 * DAY;
/** Under three hours left, the countdown is underlined. */
const URGENT = 3 * HOUR;

/** « 5 h 12 min », « 2 j 4 h », « 12 min »: the two largest units of a duration, in the locale. */
function useDuration() {
  const { locale } = useLocaleContext();
  return (ms: number) => {
    const unit = (value: number, name: "day" | "hour" | "minute") =>
      new Intl.NumberFormat(locale, { style: "unit", unit: name, unitDisplay: "short" }).format(value);
    const total = Math.max(Math.ceil(ms / MINUTE), 1);
    const days = Math.floor(total / 1440);
    const hours = Math.floor((total % 1440) / 60);
    const minutes = total % 60;
    if (days) return hours ? `${unit(days, "day")} ${unit(hours, "hour")}` : unit(days, "day");
    if (hours) return minutes ? `${unit(hours, "hour")} ${unit(minutes, "minute")}` : unit(hours, "hour");
    return unit(minutes, "minute");
  };
}

/** Where a quest stands as one bar: any one step done is enough when it completes on any of them. */
function progressOf(quest: QuestItem): Array<{ current: number; target: number }> {
  if (quest.completed) return [{ current: 1, target: 1 }];
  if (quest.complete_on === "any" && quest.steps.length > 1) {
    const best = [...quest.steps].sort((a, b) => b.current / b.target - a.current / a.target)[0];
    return best ? [best] : [];
  }
  return quest.steps;
}

/** The moment a quest still to do closes: its period's end or its window's, whichever comes first. */
function deadlineOf(quest: QuestItem): number | null {
  const ends = [quest.resets_at, quest.ends_at].filter(Boolean).map((at) => Date.parse(at as string));
  return ends.length ? Math.min(...ends) : null;
}

/** issue 307: the ones to do first, the closest deadline at the top; the done ones after, back soonest first. */
function ordered(quests: QuestItem[]): { open: QuestItem[]; done: QuestItem[] } {
  const by = (at: (q: QuestItem) => number | null) => (a: QuestItem, b: QuestItem) =>
    (at(a) ?? Number.POSITIVE_INFINITY) - (at(b) ?? Number.POSITIVE_INFINITY);
  return {
    open: quests.filter((q) => !q.completed).sort(by(deadlineOf)),
    done: quests.filter((q) => q.completed).sort(by((q) => (q.resets_at ? Date.parse(q.resets_at) : null))),
  };
}

function QuestTime({ quest, now }: { quest: QuestItem; now: number }) {
  const t = useT();
  const format = useFormat();
  const duration = useDuration();
  if (quest.completed) {
    if (!quest.resets_at) return null;
    const left = Date.parse(quest.resets_at) - now;
    return (
      <p className="quest-card__time" data-tone="next">
        <Icon name="sync" size={14} />
        {left > COUNTDOWN
          ? t("gamification:quests.backOn", { date: format.date(quest.resets_at) })
          : t("gamification:quests.backIn", { time: duration(left) })}
      </p>
    );
  }
  const deadline = deadlineOf(quest);
  if (deadline === null) return null;
  const left = deadline - now;
  return (
    <p className="quest-card__time" data-tone={left < URGENT ? "urgent" : "left"}>
      <Icon name="hourglass" size={14} />
      {left > COUNTDOWN
        ? t("gamification:quests.until", { date: format.date(new Date(deadline)) })
        : t("gamification:quests.left", { time: duration(left) })}
    </p>
  );
}

function QuestCard({ quest, now }: { quest: QuestItem; now: number }) {
  const t = useT();
  const format = useFormat();
  const text = useQuestText()(quest);
  const kind =
    quest.kind === "daily" && quest.period && quest.period !== "day" ? `daily_${quest.period}` : quest.kind;
  return (
    <li className="quest-card" id={quest.key} data-state={quest.completed ? "completed" : "open"}>
      <div className="quest-card__head">
        <span className="quest-card__icon" aria-hidden="true">
          <Icon name={quest.completed ? "check" : (quest.icon ?? "target")} size={18} />
        </span>
        <span className="quest-card__kind">{t(`gamification:quests.kind.${kind}`)}</span>
        {quest.completed ? (
          <span className="quest-card__seal">
            <Icon name="badge-check" size={14} />
            {t("gamification:quests.validated")}
          </span>
        ) : null}
      </div>
      <h4 className="quest-card__title">{text.label}</h4>
      {text.description ? <p className="quest-card__text">{text.description}</p> : null}
      {progressOf(quest).map((step, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: steps are positional
        <div key={index} className="quest-card__progress">
          <span
            className="ds-bar"
            role="progressbar"
            aria-label={t("gamification:achievements.progress", step)}
            aria-valuemin={0}
            aria-valuemax={step.target}
            aria-valuenow={Math.min(step.current, step.target)}
          >
            <span
              className="ds-bar__fill"
              style={{
                inlineSize: `${Math.round((Math.min(step.current, step.target) / step.target) * 100)}%`,
              }}
            />
          </span>
          {quest.completed ? null : (
            <span className="quest-card__count">
              {format.number(Math.min(step.current, step.target))} / {format.number(step.target)}
            </span>
          )}
        </div>
      ))}
      {quest.rewards.length || quest.gifts?.length ? (
        <p className="quest-card__rewards">
          {quest.rewards.map((reward) => (
            <span key={reward.value} className="quest-card__reward" data-value={reward.value}>
              {t("gamification:quests.reward", {
                amount: reward.amount,
                value: t(`gamification:value.${reward.value}`),
              })}
            </span>
          ))}
          {(quest.gifts ?? []).map((gift) => (
            <span key={gift} className="quest-card__reward" data-value="gift">
              {t("gamification:quests.gift", { gift })}
            </span>
          ))}
        </p>
      ) : null}
      <QuestTime quest={quest} now={now} />
    </li>
  );
}

/** issue 311: the filters — by when an objective starts again, then the quests done once and the dated
 * challenges. */
const FILTERS = ["all", "day", "week", "month", "once", "challenge"] as const;
type Filter = (typeof FILTERS)[number];
const STORED = "portalab.quests.filter";

function filterOf(quest: QuestItem): Exclude<Filter, "all"> {
  if (quest.period === "day" || quest.period === "week" || quest.period === "month") return quest.period;
  return quest.kind === "challenge" ? "challenge" : "once";
}

function storedFilter(): Filter {
  try {
    const value = localStorage.getItem(STORED);
    return FILTERS.includes(value as Filter) ? (value as Filter) : "all";
  } catch {
    return "all";
  }
}

/**
 * Quest list (spec 013 T039; issue 307 redesign): those to do first — the closest deadline at the top, its
 * time left counted down — then those done, sealed « Done » with when they come back. Kind and state in
 * **text** (never color alone); texts in the interface's language when the quest has them. Issue 311:
 * filtered by period (today, this week, this month), quests done once or challenges — each filter with
 * how many are left to do; the choice is remembered on this device.
 */
export function QuestList({ quests }: { quests: QuestItem[] }) {
  const t = useT();
  const now = useNow();
  const [chosen, setChosen] = useState<Filter>(storedFilter);
  if (quests.length === 0) return <p>{t("gamification:quests.empty")}</p>;
  const present = FILTERS.filter((f) => f === "all" || quests.some((q) => filterOf(q) === f));
  const filter = present.includes(chosen) ? chosen : "all";
  const choose = (next: Filter) => {
    setChosen(next);
    try {
      localStorage.setItem(STORED, next);
    } catch {
      // a private window keeps no choice: the filter still applies for now
    }
  };
  const left = (f: Filter) => quests.filter((q) => !q.completed && (f === "all" || filterOf(q) === f)).length;
  const { open, done } = ordered(filter === "all" ? quests : quests.filter((q) => filterOf(q) === filter));
  const groups: Array<[string, QuestItem[]]> = [
    ["open", open],
    ["done", done],
  ];
  return (
    <div className="quest-board">
      {present.length > 2 ? (
        <fieldset className="ds-subnav quest-filters" aria-label={t("gamification:quests.filter.label")}>
          {present.map((f) => (
            <button key={f} type="button" aria-pressed={filter === f} onClick={() => choose(f)}>
              {t(`gamification:quests.filter.${f}`)}
              <span className="quest-filters__count">{left(f)}</span>
            </button>
          ))}
        </fieldset>
      ) : null}
      {groups.map(([group, items]) =>
        items.length ? (
          <section key={group} className="quest-board__group" data-group={group}>
            <h3 className="quest-board__title">
              {t(`gamification:quests.group.${group}`, { count: items.length })}
            </h3>
            <ul className="quest-grid">
              {items.map((quest) => (
                <QuestCard key={quest.key} quest={quest} now={now} />
              ))}
            </ul>
          </section>
        ) : null,
      )}
    </div>
  );
}
