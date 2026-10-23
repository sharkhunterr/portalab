import type { MediaCard } from "./api";

/** Issue 229: a figure printed on a card like a trading card's attack — an icon, what it is, its value big on
 * the right (and a small unit after it). Only the work's own figures, frozen with its set; one unknown is left
 * out rather than shown empty. */
export interface Figure {
  key: "rating" | "votes" | "success" | "seasons";
  icon: string;
  big: { id: string; values: Record<string, number> };
  small?: string;
}

function rating(r: number | undefined): Figure | null {
  return r
    ? {
        key: "rating",
        icon: "star",
        big: { id: "gamification:cards.figure.ratingValue", values: { value: r } },
        small: "/10",
      }
    : null;
}

function third(card: MediaCard): Figure | null {
  const facts = card.set_facts ?? {};
  if (card.set_kind === "series") {
    return facts.seasons
      ? {
          key: "seasons",
          icon: "calendar",
          big: { id: "gamification:cards.figure.seasonsValue", values: { seasons: facts.seasons } },
        }
      : null;
  }
  if (!facts.budget || !facts.revenue) return null;
  const ratio = Math.round((facts.revenue / facts.budget) * 10) / 10;
  return {
    key: "success",
    icon: "coins",
    big: { id: "gamification:cards.figure.successValue", values: { ratio } },
  };
}

/** A work's card: its rating, its votes, its box office (a series: its seasons). Anyone else's (a role, a
 * director…): their work's rating and box office — the work is the card's subject next to them. */
export function figuresOf(card: MediaCard): Figure[] {
  const facts = card.set_facts ?? {};
  const votes: Figure | null =
    card.kind === "title" && facts.votes
      ? {
          key: "votes",
          icon: "users",
          big: { id: "gamification:cards.figure.votesValue", values: { votes: facts.votes } },
        }
      : null;
  return [rating(facts.rating), votes, third(card)].filter((f): f is Figure => f !== null);
}

/** A runtime as hours and minutes (« 2 h 43 »), its parts for the catalogue's message. */
export function runtimeParts(minutes: number | undefined): { hours: number; minutes: string } | null {
  if (!minutes) return null;
  return { hours: Math.floor(minutes / 60), minutes: String(minutes % 60).padStart(2, "0") };
}
