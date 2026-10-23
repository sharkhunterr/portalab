import type { MediaCard } from "./api";

/** Issue 229: a gauge printed on a card — what it measures, how full (0 to 10 segments, ``null``: unknown,
 * left empty) and the figure written beside it. */
export interface Gauge {
  key: "rating" | "votes" | "success" | "billing" | "work" | "seasons";
  filled: number | null;
  /** what is written: a message of the cards' catalogue and its values */
  value: { id: string; values?: Record<string, number | string> } | null;
}

const clamp = (n: number) => Math.max(0, Math.min(10, Math.round(n)));
/** fixed scales, the same for every card: a vote count from 100 to 50 000 (logarithmic), revenue from ×1 to ×10 */
const LOG_VOTES = [2, Math.log10(50_000)] as const;

function rating(r: number | undefined, key: "rating" | "work"): Gauge {
  return r
    ? { key, filled: clamp(r), value: { id: "gamification:cards.gauge.ratingValue", values: { value: r } } }
    : { key, filled: null, value: null };
}

function votes(v: number | undefined): Gauge {
  if (!v) return { key: "votes", filled: null, value: null };
  const share = (Math.log10(v) - LOG_VOTES[0]) / (LOG_VOTES[1] - LOG_VOTES[0]);
  return {
    key: "votes",
    filled: clamp(share * 10),
    value: { id: "gamification:cards.gauge.votesValue", values: { count: v } },
  };
}

function success(budget: number | undefined, revenue: number | undefined): Gauge {
  if (!budget || !revenue) return { key: "success", filled: null, value: null };
  const ratio = revenue / budget;
  return {
    key: "success",
    filled: clamp(Math.log10(Math.max(ratio, 1)) * 10),
    value: { id: "gamification:cards.gauge.successValue", values: { ratio: Math.round(ratio * 10) / 10 } },
  };
}

function seasons(n: number | undefined): Gauge {
  return n
    ? {
        key: "seasons",
        filled: clamp(n),
        value: { id: "gamification:cards.gauge.seasonsValue", values: { count: n } },
      }
    : { key: "seasons", filled: null, value: null };
}

/** The card's three gauges: only the work's own figures (never what a server holds), frozen with its set.
 * A work: its rating, its popularity, its success (a series: its seasons). A role: its place in the credits,
 * then its work's rating and success. */
export function gaugesOf(card: MediaCard): Gauge[] {
  const facts = card.set_facts ?? {};
  const third = card.set_kind === "series" ? seasons(facts.seasons) : success(facts.budget, facts.revenue);
  if (card.kind === "cast") {
    const place = (card.billing ?? 0) + 1;
    return [
      {
        key: "billing",
        filled: clamp(10 - (place - 1)),
        value: { id: "gamification:cards.gauge.billingValue", values: { place } },
      },
      rating(facts.rating, "work"),
      third,
    ];
  }
  return [rating(facts.rating, "rating"), votes(facts.votes), third];
}
