import type { Translate } from "../../../i18n/hooks/useT";
import type { Operation } from "./tuning";

type Number = (value: number) => string;

/**
 * Issue 261: how a rule reckoned a gain, as a sum — « 26 min × 1 XP/min × 1,5 (Streak bonus) = 39 XP »,
 * « 16 min × 1 XP / 3 min = 5 XP », « 5 XP » — and a limit that kept some back (« → 30 XP (limit) »). Time is
 * told in minutes, whether the rule counts seconds (``watched_s``) or minutes.
 */
export function reckoning(row: Operation, t: Translate, number: Number): string | null {
  const r = row.reckoning;
  if (!r) return null;
  const unit = t(`gamification:value.${row.value}`);
  const amount = (n: number) => `${number(n)} ${unit}`;
  const terms: string[] = [];
  if (r.fixed) terms.push(amount(r.fixed));
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
    let term = counted ? `${counted} × ${rate}` : rate;
    if (r.max != null && r.base - (r.fixed ?? 0) >= r.max) {
      term = t("gamification:admin.operations.reckon.max", { term });
    }
    terms.push(term);
  }
  let text = terms.length > 1 ? `(${terms.join(" + ")})` : (terms[0] ?? amount(r.base));
  const bonus = Math.abs(r.multiplier - 1) > 0.001;
  if (bonus) {
    // the bonus named when one alone made it (a streak), as the charts name it
    const named = (row.bonuses ?? []).filter((b) => b.factor);
    const by = named.length === 1 && named[0] ? ` (${t(`gamification:sources.${named[0].source}`)})` : "";
    text = `${text} × ${number(r.multiplier)}${by}`;
  }
  const total = Math.floor(r.base * r.multiplier);
  // a fixed amount alone says itself; anything else, its result
  if (bonus || r.field) text = `${text} = ${amount(total)}`;
  if (r.capped)
    text = `${text} → ${t("gamification:admin.operations.reckon.capped", { amount: amount(row.delta) })}`;
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
