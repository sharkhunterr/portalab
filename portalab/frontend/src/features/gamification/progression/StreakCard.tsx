import { useId } from "react";
import type { components } from "../../../api/generated/schema";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useMyStreak } from "../boost";

type Streak = components["schemas"]["MyStreakOut"];
type StreakDay = components["schemas"]["StreakDayOut"];

const ICONS: Record<StreakDay["state"], string | null> = {
  done: "flame",
  frozen: "snowflake",
  missed: null,
  pending: null,
};

/** How hot a streak burns: 0 none, 1 started, 2 a tier reached, 3 the last tier reached. */
export function heat(streak: Pick<Streak, "days" | "tiers">): number {
  if (streak.days <= 0) return 0;
  const reached = (streak.tiers ?? []).filter((tier) => streak.days >= tier.days).length;
  if (!reached) return 1;
  return reached === (streak.tiers ?? []).length ? 3 : 2;
}

/** The last days of a streak, today last: a flame each counted day, a snowflake each day a freeze covered,
 * an empty cell each missed day, a dashed one for today while it does not count yet. */
export function StreakDays({ days, compact = false }: { days: StreakDay[]; compact?: boolean }) {
  const t = useT();
  const format = useFormat();
  return (
    <ol
      className="streak-days"
      data-compact={compact || undefined}
      aria-label={t("gamification:streak.recent")}
    >
      {days.map((day) => {
        const noon = `${day.day}T12:00:00Z`; // the day itself, whatever the time zone
        const icon = ICONS[day.state];
        return (
          <li
            key={day.day}
            data-state={day.state}
            title={`${format.date(noon)} — ${t(`gamification:streak.state.${day.state}`)}`}
          >
            <span className="streak-days__cell" aria-hidden="true">
              {icon ? <Icon name={icon} size={compact ? 12 : 16} /> : null}
            </span>
            {compact ? null : <span className="streak-days__date">{format.dayMonth(noon).day}</span>}
            <span className="visually-hidden">
              {format.date(noon)} : {t(`gamification:streak.state.${day.state}`)}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/** The road of a streak: each tier a milestone with its multiplier, the streak's flame where it stands. */
export function StreakRoad({ streak }: { streak: Pick<Streak, "days" | "tiers"> }) {
  const t = useT();
  const tiers = streak.tiers ?? [];
  if (!tiers.length) return null;
  const end = Math.max(...tiers.map((tier) => tier.days));
  const at = (days: number) => `${Math.min(100, (days / end) * 100)}%`;
  return (
    <div className="streak-road">
      <div
        className="streak-road__track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={end}
        aria-valuenow={Math.min(streak.days, end)}
        aria-label={t("gamification:streak.road")}
      >
        <span className="streak-road__fill" style={{ inlineSize: at(streak.days) }} />
        {tiers.map((tier) => (
          <span
            key={tier.days}
            className="streak-road__tier"
            data-reached={streak.days >= tier.days || undefined}
            style={{ insetInlineStart: at(tier.days) }}
          >
            <span className="streak-road__dot" aria-hidden="true" />
            <span className="streak-road__label">
              <strong>×{tier.multiplier}</strong>
              <span>{t("gamification:streak.tierDay", { days: tier.days })}</span>
            </span>
          </span>
        ))}
        {streak.days > 0 ? (
          <span
            className="streak-road__marker"
            style={{ insetInlineStart: at(streak.days) }}
            aria-hidden="true"
          >
            <Icon name="flame" size={16} />
          </span>
        ) : null}
      </div>
    </div>
  );
}

/**
 * My play streak (027, #388 — progression page): its days in a big flame that burns hotter with each tier, its
 * multiplier, whether today already counts, the road to the next tiers, the last fourteen days, its record
 * and the freezes I hold.
 */
export function StreakCard() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const streak = useMyStreak().data;
  if (!streak?.enabled) return null;
  const level = heat(streak);
  const alive = streak.days > 0;
  const status = !alive
    ? t("gamification:streak.start")
    : streak.today
      ? t("gamification:streak.safe")
      : t("gamification:streak.atRisk");
  return (
    <section className="ds-card streak-card" data-heat={level} aria-labelledby={headingId}>
      <div className="streak-card__hero">
        <div className="streak-card__flame" aria-hidden="true">
          <Icon name="flame" size={56} />
          <strong>{streak.days}</strong>
        </div>
        <div className="streak-card__text">
          <h2 id={headingId}>
            {alive ? t("gamification:streak.title", { days: streak.days }) : t("gamification:streak.none")}
          </h2>
          <p className="streak-card__status" data-risk={(alive && !streak.today) || undefined}>
            <Icon name={alive && streak.today ? "check" : "clock"} size={16} /> {status}
          </p>
          <p className="streak-card__boost">
            {streak.multiplier > 1 ? (
              <span className="streak-card__multiplier">×{streak.multiplier}</span>
            ) : null}
            {streak.next
              ? t("gamification:sources.nextTier", {
                  days: streak.next.days - streak.days,
                  multiplier: streak.next.multiplier,
                })
              : alive && streak.tiers?.length
                ? t("gamification:streak.top")
                : null}
          </p>
        </div>
        <dl className="streak-card__facts">
          <div>
            <dt>{t("gamification:streak.best")}</dt>
            <dd>
              <Icon name="trophy" size={14} /> {t("gamification:streak.days", { count: streak.best ?? 0 })}
            </dd>
          </div>
          {streak.freezes ? (
            <div title={t("gamification:freeze.hint")}>
              <dt>{t("gamification:streak.freezes")}</dt>
              <dd>
                <Icon name="snowflake" size={14} /> {format.number(streak.freezes)}
              </dd>
            </div>
          ) : null}
        </dl>
      </div>
      <StreakRoad streak={streak} />
      {streak.recent?.length ? <StreakDays days={streak.recent} /> : null}
      {streak.last_frozen ? (
        <p className="streak-card__frozen">
          <Icon name="snowflake" size={14} />{" "}
          {t("gamification:freeze.used", { date: format.date(streak.last_frozen) })}
        </p>
      ) : null}
    </section>
  );
}
