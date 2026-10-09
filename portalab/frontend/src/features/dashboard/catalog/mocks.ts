import type { WidgetPayload } from "../api";

/**
 * 027: sample data for a widget's miniature when the member has nothing to show yet (an empty list, no
 * plays, a note not written) — so the catalog and the shop still show what the widget looks like. Only for
 * previews: never stored, never on the dashboard. Keyed by component (else by template).
 */
const day = 24 * 3600 * 1000;
const inDays = (n: number) => new Date(Date.now() + n * day).toISOString();
const TITLES = [
  ["Dune: Part Two", "movie", "2024"],
  ["Arcane", "series", "S2"],
  ["The Last of Us", "series", "S2E3"],
  ["Oppenheimer", "movie", "2023"],
  ["Severance", "series", "S2"],
  ["Spirited Away", "movie", "2001"],
  ["The Legend of Zelda", "game", "NES"],
  ["Project Hail Mary", "book", "2021"],
] as const;
const cards = (n: number) =>
  TITLES.slice(0, n).map(([title, kind, meta], i) => ({
    id: `sample-${i}`,
    title,
    kind,
    meta,
    at: inDays(-i),
    plays: 12 - i,
    route: "/media",
  }));
const points = (base: number) => Array.from({ length: 12 }, (_, i) => [i + 1, base + ((i * 7) % 9) + i]);

const MOCKS: Record<string, () => Record<string, unknown>> = {
  list: () => ({
    items: cards(5).map((c) => ({ title: c.title, meta: `${c.kind} · ${c.meta}`, route: c.route })),
  }),
  timeline: () => ({ items: cards(4).map((c) => ({ title: c.title, at: c.at, meta: c.meta })) }),
  chart: () => ({
    label: "Plays",
    value: 128,
    series: [
      { label: "Films", points: points(4) },
      { label: "Series", points: points(8) },
    ],
  }),
  stat: () => ({ label: "Plays", value: 128, previous: 96 }),
  "community.projects": () => ({
    items: [
      { id: "s1", title: "Dark mode for the wiki", help_wanted: false, votes: 14 },
      { id: "s2", title: "A retro gaming night", help_wanted: true, votes: 9 },
      { id: "s3", title: "4K for the classics", help_wanted: false, votes: 6 },
    ],
  }),
  "dashboard.note": () => ({ text: "Movie night on Friday — bring the popcorn! 🍿", color: "yellow" }),
  "dashboard.countdown": () => ({ label: "Movie night", date: inDays(3) }),
  "media.posters": () => ({ items: cards(6), mode: "added" }),
  "media.wall": () => ({ items: cards(8) }),
  "media.shuffle": () => ({
    items: cards(6).map((c) => ({
      ...c,
      year: 2024,
      genres: ["Sci-Fi"],
      overview: "A crew far from home, a signal nobody expected.",
    })),
  }),
  "media.continue": () => ({
    items: cards(3).map((c, i) => ({ ...c, subtitle: c.meta, progress: 0.25 + i * 0.25 })),
  }),
  "media.living_wall": () => ({
    items: [...cards(8), ...cards(8)].map((c, i) => ({ ...c, id: `wall-${i}` })),
  }),
  "media.server_playing": () => ({
    count: 3,
    items: cards(3).map((c, i) => ({
      ...c,
      subtitle: c.kind === "series" ? c.meta : null,
      state: i === 1 ? "paused" : "playing",
      progress: 0.2 + i * 0.3,
      remaining_s: 3600 - i * 900,
      mine: i === 0,
    })),
  }),
  "media.next_releases": () => ({
    items: cards(4).map((c, i) => ({
      ...c,
      at: inDays(i * 4 + 2),
      reason: i % 2 ? "requested" : "watching",
      type: c.kind === "series" ? "air" : "digital",
    })),
  }),
  "media.on_this_day": () => ({
    moments: [
      { years: 1, date: inDays(-365).slice(0, 10), watched: cards(3), added: cards(7).slice(3) },
      { years: 2, date: inDays(-730).slice(0, 10), watched: cards(2), added: [] },
    ],
  }),
  "media.soon": () => ({
    items: cards(3).map((c, i) => ({
      ...c,
      request_id: c.id,
      state: "processing",
      phase: i ? "release" : "download",
      requested_at: inDays(-2),
      release_at: inDays(i + 1),
    })),
  }),
};

/** Whether a payload has nothing to show (no data, or only empty lists). */
function empty(payload: WidgetPayload | undefined): boolean {
  if (!payload || payload.state === "no-data") return true;
  const data = payload.data as Record<string, unknown> | null | undefined;
  if (!data) return true;
  const items = data.items;
  return Array.isArray(items) && items.length === 0;
}

/** The payload a miniature shows: the member's own, else a sample when the widget has one. */
export function previewPayload(
  payload: WidgetPayload | undefined,
  component: string | null | undefined,
  template: string | null | undefined,
): { payload: WidgetPayload; sample: boolean } | null {
  if (payload && ["unauthorized", "error", "unavailable"].includes(String(payload.state))) return null;
  if (payload && !empty(payload)) return { payload, sample: false };
  const make = (component && MOCKS[component]) || (template && MOCKS[template]);
  if (!make) return payload && payload.state !== "no-data" ? { payload, sample: false } : null;
  return {
    payload: {
      state: "available",
      as_of: null,
      stale_after_s: null,
      data: make(),
      partial_reasons: [],
      config_invalid: false,
    } as WidgetPayload,
    sample: true,
  };
}
