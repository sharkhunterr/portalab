import type { Translate } from "../../../i18n/hooks/useT";
import type { Operation } from "./tuning";

type Number = (value: number) => string;

/**
 * Issue 261: how a rule reckoned a gain, said in a line — « 51 min × 1 XP/min = 51 XP », « 16 min × 1 XP / 3 min
 * = 5 XP », « 5 XP fixed » — then its bonuses' multiplier (a streak's ×1.5) and a limit that kept some back.
 * Time is told in minutes, whether the rule counts seconds (``watched_s``) or minutes.
 */
export function reckoning(row: Operation, t: Translate, number: Number): string | null {
  const r = row.reckoning;
  if (!r) return null;
  const unit = t(`gamification:value.${row.value}`);
  const amount = (n: number) => `${number(n)} ${unit}`;
  let text: string;
  if (r.field && r.factor) {
    const seconds = r.field.endsWith("_s");
    const timed = seconds || r.field === "minutes";
    const perMinute = seconds ? r.factor * 60 : r.factor;
    const rate = !timed
      ? t("gamification:admin.operations.reckon.rateUnit", { amount: number(r.factor), unit, field: r.field })
      : perMinute >= 1
        ? t("gamification:admin.operations.reckon.rate", { amount: number(perMinute), unit })
        : t("gamification:admin.operations.reckon.rateEvery", { every: Math.round(1 / perMinute), unit });
    const counted =
      r.quantity == null
        ? null
        : timed
          ? t("gamification:admin.operations.reckon.minutes", {
              count: Math.floor(seconds ? r.quantity / 60 : r.quantity),
            })
          : t("gamification:admin.operations.reckon.units", { quantity: number(r.quantity), field: r.field });
    const part = r.base - (r.fixed ?? 0);
    let per = counted
      ? t("gamification:admin.operations.reckon.perUnit", { quantity: counted, rate, amount: amount(part) })
      : t("gamification:admin.operations.reckon.rateOnly", { rate, amount: amount(part) });
    if (r.max != null && part >= r.max) {
      per = t("gamification:admin.operations.reckon.max", { text: per, max: amount(r.max) });
    }
    text = r.fixed
      ? t("gamification:admin.operations.reckon.plus", {
          fixed: amount(r.fixed),
          part: per,
          total: amount(r.base),
        })
      : per;
  } else {
    text = t("gamification:admin.operations.reckon.fixed", { amount: amount(r.base) });
  }
  if (Math.abs(r.multiplier - 1) > 0.001) {
    text = t("gamification:admin.operations.reckon.bonus", {
      text,
      factor: number(r.multiplier),
      total: amount(Math.floor(r.base * r.multiplier)),
    });
  }
  if (r.capped) {
    text = t("gamification:admin.operations.reckon.capped", { text, amount: amount(row.delta) });
  }
  return text;
}

/** Issue 261: the work a gain was about — an episode with its series and season (« Sissi · S2 E6 »). */
export function workOf(row: Operation, t: Translate): { name: string; part: string | null } | null {
  const work = row.work;
  if (!work) return row.title ? { name: row.title, part: null } : null;
  if (work.kind === "episode" && work.series) {
    const at = t("gamification:admin.operations.episode", {
      season: work.season ?? "?",
      number: work.number ?? "?",
    });
    // « Épisode 6 » says nothing the number does not
    return {
      name: `${work.series} · ${at}`,
      part: /^(é|e)pisode \d+$/i.test(work.title) ? null : work.title,
    };
  }
  return { name: work.year ? `${work.title} (${work.year})` : work.title, part: null };
}
