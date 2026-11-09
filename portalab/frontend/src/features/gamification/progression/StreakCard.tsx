import { Fragment, useId } from "react";
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
      {days.map((day, index) => {
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
            {compact ? null : (
              <span
                className="streak-days__date"
                data-today={index === days.length - 1 || undefined}
              >
                {index === days.length - 1 ? t("gamification:streak.todayShort") : format.weekday(noon)}
              </span>
            )}
            <span className="visually-hidden">
              {format.date(noon)} : {t(`gamification:streak.state.${day.state}`)}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/** The last fourteen days as their own block: a title with the active days counted, the strip, a legend. */
function StreakHistory({ days }: { days: StreakDay[] }) {
  const t = useT();
  const format = useFormat();
  const active = days.filter((day) => day.state === "done" || day.state === "frozen").length;
  const first = days[0];
  return (
    <div className="streak-history">
      <div className="streak-road__head">
        <strong>{t("gamification:streak.history", { count: days.length })}</strong>
        <span>
          {t("gamification:streak.active", { count: active, total: days.length })}
          {first
            ? ` · ${t("gamification:streak.since", { date: format.date(`${first.day}T12:00:00Z`) })}`
            : ""}
        </span>
      </div>
      <StreakDays days={days} />
      <ul className="streak-legend" aria-hidden="true">
        {(["done", "frozen", "missed", "pending"] as const).map((state) => (
          <li key={state} data-state={state}>
            <span className="streak-days__cell">
              {ICONS[state] ? <Icon name={ICONS[state] ?? ""} size={10} /> : null}
            </span>
            {t(`gamification:streak.legend.${state}`)}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The road of a streak: a bar cut at each tier — every stretch filling as the days go by, every tier a
 * milestone with its multiplier that lights up once reached —, the streak's flame where it stands. */
export function StreakRoad({ streak }: { streak: Pick<Streak, "days" | "tiers"> }) {
  const t = useT();
  const tiers = [...(streak.tiers ?? [])].sort((a, b) => a.days - b.days);
  if (!tiers.length) return null;
  const last = tiers.at(-1)?.days ?? 0;
  const days = streak.days;
  const stops = [{ days: 0, multiplier: 1 }, ...tiers];
  const next = tiers.find((tier) => tier.days > days);
  return (
    <div className="streak-road">
      <div className="streak-road__head">
        <strong>{t("gamification:streak.road")}</strong>
        <span>
          {next
            ? t("gamification:streak.dayOf", { days, end: next.days, multiplier: next.multiplier })
            : t("gamification:streak.top")}
        </span>
      </div>
      <div
        className="streak-road__track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={last}
        aria-valuenow={Math.min(days, last)}
        aria-valuetext={t("gamification:streak.days", { count: days })}
        aria-label={t("gamification:streak.road")}
      >
        {stops.map((stop, index) => {
          const from = stops[index - 1];
          const share = from ? Math.min(1, Math.max(0, (days - from.days) / (stop.days - from.days))) : 0;
          const here = from !== undefined && days > from.days && days < stop.days;
          return (
            <Fragment key={stop.days}>
              {from ? (
                <span
                  className="streak-road__stretch"
                  style={{ flexGrow: stop.days - from.days }}
                  data-full={share >= 1 || undefined}
                >
                  <span className="streak-road__fill" style={{ inlineSize: `${share * 100}%` }} />
                  {here ? (
                    <span className="streak-road__marker" style={{ insetInlineStart: `${share * 100}%` }}>
                      <Icon name="flame" size={14} />
                    </span>
                  ) : null}
                </span>
              ) : null}
              <span
                className="streak-road__tier"
                data-reached={days >= stop.days || undefined}
                data-current={stop === next || undefined}
              >
                <span className="streak-road__badge">×{stop.multiplier}</span>
                <span className="streak-road__label">
                  {stop.days
                    ? t("gamification:streak.tierDay", { days: stop.days })
                    : t("gamification:streak.begin")}
                </span>
              </span>
            </Fragment>
          );
        })}
      </div>
    </div>
  );
}

/** A streak's road in a line (the administrators' table): the days towards the last tier, a tick at each. */
export function StreakMeter({ streak }: { streak: Pick<Streak, "days" | "tiers"> }) {
  const tiers = streak.tiers ?? [];
  if (!tiers.length) return null;
  const last = Math.max(...tiers.map((tier) => tier.days));
  return (
    <span
      className="streak-meter"
      data-heat={heat(streak)}
      aria-hidden="true" // the chip beside it tells the days
    >
      <span
        className="streak-meter__fill"
        style={{ inlineSize: `${Math.min(1, streak.days / last) * 100}%` }}
      />
      {tiers.map((tier) => (
        <span
          key={tier.days}
          className="streak-meter__tick"
          data-reached={streak.days >= tier.days || undefined}
          style={{ insetInlineStart: `${(tier.days / last) * 100}%` }}
        />
      ))}
    </span>
  );
}

/**
 * My play streak (027, issue 388 — progression page): its days in a big flame that burns hotter with each tier, its
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
            <Icon name={alive && streak.today ? "check" : "clock"} size={16} />
            <span>{status}</span>
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
      {streak.recent?.length ? <StreakHistory days={streak.recent} /> : null}
      {streak.last_frozen ? (
        <p className="streak-card__frozen">
          <Icon name="snowflake" size={14} />{" "}
          {t("gamification:freeze.used", { date: format.date(streak.last_frozen) })}
        </p>
      ) : null}
    </section>
  );
}
