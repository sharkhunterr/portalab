import type { Page, Route } from "@playwright/test";
import { MASTER, PROFILE, stubPortal } from "../support/portal";

/**
 * Issue 459 — the portal every guided tour walks over, stubbed: the pages the tours open (media, retro
 * games, requests, statistics, progression, games, cards, the shop, projects, community, calendar, support,
 * the assistant, services, news and feed, settings, the household) answer with small but real data, so each
 * step's element shows. Registered after ``stubPortal``: these routes win, anything else falls back to it
 * (whose last resort answers ``{ items: [] }``).
 */
export interface TourPortalOptions {
  /** signed in as a household profile of the master, without requests nor retro games */
  profile?: boolean;
}

/** What a handler answers: a body (sent as JSON, 200), or a full reply. */
interface Reply {
  status: number;
  body?: unknown;
  contentType?: string;
  raw?: string;
}
type Answer = unknown | ((url: URL, route: Route) => unknown);
type Handler = [method: "GET" | "POST" | "PUT" | "*", path: RegExp, answer: Answer];

const reply = (status: number, body?: unknown): Reply => ({ status, body });
const isReply = (value: unknown): value is Reply =>
  typeof value === "object" && value !== null && (value as { __reply?: boolean }).__reply === true;
const make = (r: Reply) => Object.assign(r, { __reply: true });
const notFound = () => make(reply(404, { code: "not_found", title: "Not found", status: 404 }));
const noContent = () => make(reply(204));

const DAY = 86_400_000;
const at = (days: number) => new Date(Date.now() + days * DAY).toISOString();
const dayOf = (days: number) => at(days).slice(0, 10);

/** Every permission a member may hold on the member side of the portal. */
export const PERMISSIONS = [
  "users.self.manage",
  "media.read",
  "media.play",
  "media.request",
  "retro.play",
  "requests.ask",
  "search.use",
  "services.read",
  "incidents.read",
  "tickets.create",
  "feedback.submit",
  "feedback.read",
  "marketplace.read",
  "community.read",
  "campaigns.read",
  "calendar.read",
  "news.read",
  "statistics.read",
  "games.play",
  "wiki.read",
];

type NavItem = [key: string, label: string, route: string, icon: string];

/** Every page a tour opens, in the navigation (the guide offers only the tours of reachable pages). */
const SECTIONS: Array<[key: string, icon: string, entries: NavItem[]]> = [
  ["home", "home", [["shell.home", "nav.home", "/", "home"]]],
  [
    "media",
    "film",
    [
      ["media.home", "nav.media", "/media", "film"],
      ["media.browse", "nav.mediaBrowse", "/media/browse", "search"],
      ["media.requests", "nav.requests", "/media/requests", "inbox"],
    ],
  ],
  ["statistics", "chart", [["statistics.home", "nav.statistics", "/statistics", "chart"]]],
  [
    "play",
    "game",
    [
      ["gamification.progression", "nav.progression", "/progression", "trophy"],
      ["games.home", "nav.games", "/games", "game"],
      ["cards.collection", "nav.cards", "/cards", "layers"],
    ],
  ],
  [
    "marketplace",
    "shop",
    [
      ["marketplace.vitrine", "nav.marketplace", "/marketplace", "shop"],
      ["marketplace.reserve", "nav.reserve", "/marketplace/reserve", "gift"],
    ],
  ],
  [
    "community",
    "users",
    [
      ["community.home", "nav.community", "/community", "users"],
      ["community.members", "nav.members", "/community/members", "users"],
      ["projects.home", "nav.projects", "/projects", "target"],
      ["calendar.home", "nav.calendar", "/calendar", "calendar"],
    ],
  ],
  [
    "news",
    "newspaper",
    [
      ["news.home", "nav.news", "/news", "newspaper"],
      ["media.feed", "nav.feed", "/feed", "rss"],
    ],
  ],
  [
    "support",
    "lifebuoy",
    [
      ["support.tickets", "nav.support", "/support", "lifebuoy"],
      ["health.services", "nav.services", "/services", "server"],
    ],
  ],
];
const PERSONAL: NavItem[] = [
  ["identity.account", "nav.account", "/account", "user"],
  ["settings.home", "nav.settings", "/settings", "settings"],
  ["ui.appearance", "nav.appearance", "/settings/appearance", "palette"],
  ["onboarding.guide", "nav.guide", "/guide", "compass"],
  ["shell.household", "nav.household", "/household", "users"],
];

function navigation() {
  const entry = ([key, label_key, route, icon]: NavItem) => ({ key, label_key, route, icon });
  return {
    version: "v1",
    degraded: false,
    // the 004 shape, still served (the guide reads which pages are reachable from it)
    groups: [
      {
        key: "main",
        label_key: "nav.group.main",
        entries: SECTIONS.flatMap(([, , items]) => items.map(entry)),
      },
      { key: "me", label_key: "nav.group.me", entries: PERSONAL.map(entry) },
    ],
    sections: SECTIONS.map(([key, icon, items]) => ({
      key,
      label_key: `nav.section.${key}`,
      icon,
      audience: "everyone",
      direct: items.length === 1,
      topics: [],
      entries: items.map(entry),
    })),
    personal: PERSONAL.map(entry),
    commands: [],
    related: {},
    crumbs: {},
  };
}

// --- the library: a film, a game with its saves, a title asked for ---------------------------------

const MOVIE = "00000000-0000-7000-8000-0000000000a1";
const GAME = "00000000-0000-7000-8000-0000000000a2";
const ASKED = "00000000-0000-7000-8000-0000000000a3";

const card = (id: string, title: string, kind: string, extra: Record<string, unknown> = {}) => ({
  id,
  title,
  kind,
  year: 2021,
  available: true,
  image_id: null,
  at: at(-2),
  episode: null,
  age: 12,
  kept: false,
  locked: false,
  requested: false,
  ...extra,
});
const CARDS = {
  [MOVIE]: card(MOVIE, "The Long Night", "movie"),
  [GAME]: card(GAME, "Pixel Quest", "game", { age: 7 }),
  [ASKED]: card(ASKED, "Northern Lights", "movie", { available: false, requested: true, age: null }),
};

function detail(id: string) {
  const base = CARDS[id as keyof typeof CARDS];
  if (!base) return notFound();
  return {
    ...base,
    genres: ["Drama"],
    ids: {},
    overview: "A title of the stubbed library.",
    parent_id: null,
    position: null,
    sections: [],
    status: base.available ? "available" : "requested",
    platform: base.kind === "game" ? "snes" : null,
    restricted: null,
    age_rating: {
      age: base.age,
      country: "FR",
      ratings: base.age === null ? [] : [{ source: "CNC", value: `-${base.age}` }],
    },
  };
}

const retroGame = {
  title: "Pixel Quest",
  core: "snes9x",
  engine: "emulatorjs",
  platform: "snes",
  threads: false,
  rom: "rom-1",
  variant: null,
  service_name: "RomM",
  control_scheme: null,
  progress: null,
  roms: [
    {
      id: "rom-1",
      core: "snes9x",
      engine: "emulatorjs",
      platform: "snes",
      size: 1_048_576,
      variant: null,
      progress: {
        latest_slot: 1,
        slots: 4,
        sram_at: null,
        states: [
          { slot: 0, size: 2048, has_picture: false, updated_at: at(-1) },
          { slot: 1, size: 2048, has_picture: false, updated_at: at(-3) },
        ],
      },
    },
  ],
};

const journey = {
  kind: "movie",
  available: false,
  request: { state: "pending", requested_at: at(-3) },
  manager: null,
  steps: [
    { key: "requested", status: "done", at: at(-3), by: { me: true, name: "Alex" } },
    { key: "approved", status: "current" },
    { key: "available", status: "upcoming" },
  ],
  can_search: false,
  search: null,
};

const requestCard = {
  request_id: "00000000-0000-7000-8000-0000000000b1",
  id: ASKED,
  title: "Northern Lights",
  kind: "movie",
  state: "pending",
  requested_at: at(-3),
  updated_at: at(-1),
  image_id: null,
  route: `/media/${ASKED}`,
  stage: "pending",
};

const insights = {
  period: { key: "365d", start: at(-365) },
  summary: { total: 3, pending: 1, approved: 0, available: 2, declined: 0 },
  previous_total: 1,
  by_kind: { movie: 2, series: 1 },
  timeline: {
    unit: "month",
    points: [
      { date: dayOf(-60), count: 1, previous: 0 },
      { date: dayOf(-30), count: 2, previous: 1 },
    ],
  },
  watched: { requested: 2, watched: 1, rate: 0.5 },
  ranking: { position: 2, total: 5, count: 3, delta: 1 },
  top_watched: [],
  genres: { requested: [{ name: "Drama", value: 2 }], watched: [{ name: "Drama", value: 1 }] },
  quota: { base_remaining: 4, extra_units: 0 },
};

// --- statistics, progression, games, cards ----------------------------------------------------------

const statEntry = (key: string, viz: string) => ({
  key,
  title_key: `statistics:title`,
  description_key: null,
  domain: "media",
  scope: "community",
  viz,
  period_options: ["last_n_days"],
  hidden: false,
  hideable: true,
  locked: false,
  unlock_hint: null,
});
const statResult = (key: string) => ({
  key,
  state: "available",
  value: 42,
  as_of: at(0),
  definition_version: 1,
  period_start: at(-30),
  period_end: at(0),
  series: [-3, -2, -1, 0].map((d, i) => ({ day: dayOf(d), value: 8 + i })),
  breakdown: [],
  source_states: {},
  trend: { delta: 4, direction: "up", percent: 10, previous_value: 38 },
  unlock_hint: null,
});

const quest = (key: string, period: string, completed: boolean) => ({
  key,
  kind: period === "day" ? "daily" : "quest",
  label: `Quest ${key}`,
  description: "Watch a title.",
  icon: "target",
  period,
  ends_at: at(period === "day" ? 0.5 : 4),
  resets_at: at(period === "day" ? 0.5 : 4),
  completed,
  steps: [{ current: completed ? 1 : 0, target: 1 }],
  rewards: [{ value: "xp", amount: 20 }],
});
const QUESTS = [quest("watch", "day", false), quest("read", "week", false), quest("play", "week", true)];

const mediaCard = (n: number, owned: number) => ({
  id: `card-${n}`,
  set: "set-1",
  set_code: "TLN",
  set_name: "The Long Night",
  set_size: 3,
  set_kind: "movie",
  year: 2021,
  number: n,
  kind: n === 1 ? "title" : "cast",
  person: n === 1 ? null : `person-${n}`,
  name: n === 1 ? "The Long Night" : `Actor ${n}`,
  role: null,
  flavor: null,
  art: null,
  alt_art: null,
  rarity: n === 1 ? "rare" : "common",
  retired: false,
  owned: owned ? { normal: owned } : {},
});
const cardSet = {
  key: "set-1",
  code: "TLN",
  name: "The Long Night",
  kind: "movie",
  year: 2021,
  poster: null,
  saga: null,
  size: 3,
  owned: 2,
};
const cardPack = {
  id: "pack-1",
  source: "watch",
  set: "set-1",
  set_name: "The Long Night",
  look: null,
  given_at: at(-1),
  opened_at: null,
  cards: [],
  count: 3,
};

// --- the shop --------------------------------------------------------------------------------------

const product = (key: string, type: string, extra: Record<string, unknown> = {}) => ({
  key,
  type,
  name: `Product ${key}`,
  names: {},
  descriptions: {},
  category: null,
  icon: null,
  price_coins: 50,
  price_now: 50,
  rarity: "rare",
  featured: true,
  owned: false,
  locked: false,
  repeatable: true,
  state: "active",
  version: 1,
  conditions: [],
  eligibility: [],
  config_required: false,
  refund_policy: {},
  preview: {},
  poster_effect: "",
  booster: null,
  discount: null,
  remaining: null,
  supply: null,
  limit_count: null,
  limit_days: null,
  min_level: null,
  min_contribution: null,
  season: null,
  theme: null,
  ...extra,
});
const PRODUCTS = [
  product("frame-gold", "frame"),
  product("looks-booster", "booster", { price_coins: 80, price_now: 80 }),
  product("cards-booster", "card_booster", { price_coins: 30, price_now: 30 }),
  product("ai-daily", "ai_capacity", { price_coins: 60, price_now: 60, featured: false }),
  product("streak-freeze", "consumable", {
    price_coins: 20,
    price_now: 16,
    featured: false,
    discount: { campaign: "autumn", name: "Autumn sale", names: {}, percent: 20, ends_at: at(3) },
  }),
];

// --- the household: a master, two profiles, a request waiting ---------------------------------------

const restrictions = {
  max_age: 12,
  allow_unrated: false,
  blocked: [],
  genres: [],
  titles: [],
  types: [],
  mode: "hide",
  requests: true,
  services: true,
  screen_scope: "media",
  daily_minutes: 90,
  week_minutes: null,
  hours_from: "08:00",
  hours_to: "20:00",
  slots: [],
  birth_date: null,
};
const figures = (xp: number) => ({ xp, level: 2, coins: 30, contribution: 1 });
function household(profile: boolean) {
  const kid = (id: string, display_name: string, color: string) => ({
    id,
    display_name,
    kind: "child",
    color,
    has_avatar: false,
    has_pin: false,
    community_visible: false,
    progress: figures(40),
    age: 10,
    effective_age: 10,
    bonus_minutes: 0,
    free_until: null,
    needs_pin: false,
    restrictions,
  });
  return {
    enabled: true,
    owner_id: MASTER,
    me: profile ? PROFILE : MASTER,
    can_manage: !profile,
    max_profiles: 8,
    palette: ["#6366f1", "#ec4899", "#22c55e"],
    totals: figures(200),
    economy: "pot",
    members: [
      {
        id: MASTER,
        display_name: "Alex",
        kind: "owner",
        color: "#6366f1",
        has_avatar: false,
        has_pin: false,
        community_visible: true,
        progress: figures(120),
      },
      kid(PROFILE, "Léa", "#ec4899"),
      kid("00000000-0000-7000-8000-0000000000c2", "Tom", "#22c55e"),
    ],
  };
}
const screenTime = {
  allowed: 90,
  used: 35,
  open: true,
  scope: "media",
  slot: null,
  next: null,
  slots: [{ start: "08:00", end: "20:00", minutes: null }],
};

// --- the assistant: one answer with its sources -------------------------------------------------------

const answer = [
  `event: delta\ndata: ${JSON.stringify({ text: "Media is up." })}`,
  `event: done\ndata: ${JSON.stringify({
    content: "Media is up and running [1].",
    sources: [
      {
        n: 1,
        kind: "services",
        ref: "s0",
        title: "Media",
        class: "real",
        as_of: at(0),
        url: "/services",
        detail: "Operational",
      },
    ],
    caveats: [],
    interpretation: false,
    pending_actions: [],
    message_id: "00000000-0000-7000-8000-0000000000d1",
  })}`,
].join("\n\n");

/** The routes of the pages the tours open, then a record of what was posted (the tours' end is one). */
export async function stubTourPortal(page: Page, options: TourPortalOptions = {}) {
  const profile = options.profile ?? false;
  const portal = await stubPortal(page, { made: true, profile });
  const posted: string[] = [];
  // the requests no handler here answered, and what broke on the page — printed when a tour fails
  const unanswered = new Set<string>();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(`${page.url()}: ${error.message}`));
  // a page's error boundary says it in the console only
  page.on("console", (message) => {
    if (message.type() === "error" && !/Failed to load resource|EventSource/.test(message.text()))
      errors.push(`${page.url()}: ${message.text().slice(0, 300)}`);
  });
  const media = (url: URL) => {
    const kind = url.searchParams.get("kind");
    const items = kind ? Object.values(CARDS).filter((c) => c.kind === kind) : Object.values(CARDS);
    return { items, next_cursor: null, total: items.length };
  };
  const handlers: Handler[] = [
    ["GET", /^\/api\/v1\/me\/navigation$/, navigation()],
    [
      "GET",
      /^\/api\/v1\/me\/permissions$/,
      {
        permissions: profile
          ? PERMISSIONS.filter((p) => p !== "media.request" && p !== "retro.play")
          : PERMISSIONS,
        roles: ["user"],
      },
    ],
    // the end of a tour (and the portal's first step)
    ["POST", /^\/api\/v1\/me\/onboarding\/.+\/complete$/, noContent],
    ["GET", /^\/api\/v1\/me\/quests$/, []],
    // the assistant: on, with a day's allowance (its meter), and an answer with its sources
    [
      "GET",
      /^\/api\/v1\/ai\/status$/,
      {
        available: true,
        provider_state: "ok",
        auto_navigate: false,
        name: "",
        daily_budget: 20_000,
        used_today: 5_000,
        recharge: 0,
        perks: {},
        shop: true,
        ideas: [],
      },
    ],
    ["GET", /^\/api\/v1\/ai\/conversations$/, []],
    [
      "POST",
      /^\/api\/v1\/ai\/conversations$/,
      { id: "00000000-0000-7000-8000-0000000000d0", title: "", created_at: at(0), updated_at: at(0) },
    ],
    [
      "POST",
      /^\/api\/v1\/ai\/conversations\/[^/]+\/messages$/,
      () => make({ status: 200, contentType: "text/event-stream", raw: `${answer}\n\n` }),
    ],
    // the library
    ["GET", /^\/api\/v1\/media$/, media],
    ["GET", /^\/api\/v1\/media\/facets$/, { genres: ["Drama"], years: { min: 1990, max: 2026 } }],
    ["GET", /^\/api\/v1\/media\/[0-9a-f-]{36}$/, (url: URL) => detail(url.pathname.split("/").pop() ?? "")],
    [
      "GET",
      /^\/api\/v1\/media\/[0-9a-f-]{36}\/journey$/,
      (url: URL) => (url.pathname.includes(ASKED) ? journey : notFound()),
    ],
    ["GET", new RegExp(`^/api/v1/retro/games/${GAME}$`), retroGame],
    ["GET", /^\/api\/v1\/retro\/games\/[^/]+$/, notFound],
    // a title's other parts (metadata, sections, player…): none — each says so on its own
    ["GET", /^\/api\/v1\/media\/[0-9a-f-]{36}\/.+$/, notFound],
    [
      "GET",
      /^\/api\/v1\/retro\/accounts$/,
      [{ service_id: "romm", service_name: "RomM", state: "linked", username: "alex", interval: 5 }],
    ],
    // my requests
    ["GET", /^\/api\/v1\/me\/media\/requests\/insights$/, insights],
    ["GET", /^\/api\/v1\/me\/media\/requests\/list$/, { items: [requestCard] }],
    ["GET", /^\/api\/v1\/me\/media\/requests\/soon$/, { items: [] }],
    // statistics and progression
    [
      "GET",
      /^\/api\/v1\/statistics\/catalog$/,
      [statEntry("media.plays", "number"), statEntry("media.trend", "line")],
    ],
    ["GET", /^\/api\/v1\/statistics\/[^/]+$/, (url: URL) => statResult(url.pathname.split("/").pop() ?? "")],
    ["GET", /^\/api\/v1\/me\/statistics\/preferences$/, { hidden: [] }],
    [
      "GET",
      /^\/api\/v1\/me\/progression\/sources$/,
      {
        value: "xp",
        total: 120,
        sources: [
          { source: "plays", amount: 80 },
          { source: "quests", amount: 40 },
        ],
        days: [{ day: dayOf(-1), amounts: { plays: 30, quests: 10 } }],
      },
    ],
    [
      "GET",
      /^\/api\/v1\/me\/achievements$/,
      [
        {
          key: "first_watch",
          state: "unlocked",
          label: "First watch",
          description: "Watch a first title.",
          icon: "star",
          unlocked_at: at(-5),
          progress: [{ current: 1, target: 1 }],
          category: "media",
          unlock_share: 0.4,
          rarity: "common",
          rewards: [{ value: "xp", amount: 10 }],
          unlocks: [],
        },
      ],
    ],
    [
      "GET",
      /^\/api\/v1\/(community\/)?leaderboards\/[^/]+$/,
      {
        metric: "xp",
        period: "week",
        state: "ok",
        computed_at: at(0),
        entries: [{ rank: 1, user_id: MASTER, display_name: "Alex", score: 240, me: true }],
        me: { rank: 1, user_id: MASTER, display_name: "Alex", score: 240, me: true },
      },
    ],
    // games and quests
    [
      "GET",
      /^\/api\/v1\/games$/,
      {
        enabled: true,
        games: [{ key: "poster", kind: "quiz", solo: true, party: true, rounds: 5 }],
        party: true,
        cinemot: null,
        parties: [],
      },
    ],
    ["GET", /^\/api\/v1\/games\/leaderboard$/, { game: "poster", period: "week", entries: [], me: null }],
    ["GET", /^\/api\/v1\/community\/quests$/, { state: "ok", items: QUESTS }],
    ["GET", /^\/api\/v1\/campaigns\/active$/, []],
    [
      "GET",
      /^\/api\/v1\/me\/wheel$/,
      {
        enabled: true,
        day: dayOf(0),
        next_at: at(1),
        spin_ms: 4000,
        coins: 120,
        today: null,
        segments: [
          { key: "c10", kind: "coins", amount: 10 },
          { key: "x20", kind: "xp", amount: 20 },
          { key: "none", kind: "nothing", amount: 0 },
        ],
      },
    ],
    // the cards
    [
      "GET",
      /^\/api\/v1\/me\/cards$/,
      { unique: 2, copies: 3, sets_started: 1, cards: 3, sets: 1, unopened: 1 },
    ],
    ["GET", /^\/api\/v1\/cards\/sets$/, { total: 1, items: [cardSet] }],
    [
      "GET",
      /^\/api\/v1\/cards\/sets\/[^/]+$/,
      { ...cardSet, present: true, cards: [mediaCard(1, 1), mediaCard(2, 2), mediaCard(3, 0)] },
    ],
    ["GET", /^\/api\/v1\/me\/cards\/packs$/, [cardPack]],
    // the shop and my reserve
    ["GET", /^\/api\/v1\/marketplace\/products$/, PRODUCTS],
    [
      "GET",
      /^\/api\/v1\/marketplace\/reserve$/,
      [
        { product: PRODUCTS[1], quantity: 1, needs_configuration: false, booster: true },
        { product: PRODUCTS[4], quantity: 2, needs_configuration: false, booster: false },
      ],
    ],
    ["GET", /^\/api\/v1\/me\/marketplace\/purchases$/, []],
    // projects
    [
      "GET",
      /^\/api\/v1\/projects$/,
      [
        {
          id: "00000000-0000-7000-8000-0000000000e1",
          title: "A 4K film night",
          state: "open",
          proposal_ref: "p-1",
          accepts_funding: true,
          accepts_votes: false,
          funding_rules: null,
          rules_frozen_at: null,
          updated_at: at(-1),
          version: 1,
          history: [],
          notes: [],
          totals: { reserved: 120, consumed: 0, funders: 3, goal_amount: 500 },
        },
      ],
    ],
    ["GET", /^\/api\/v1\/me\/fundings$/, []],
    // the community
    [
      "GET",
      /^\/api\/v1\/community\/discovery$/,
      [
        { key: "new_members", label_key: "community:discovery.shelf.new_members", empty_action: null },
        { key: "recent_unlocks", label_key: "community:discovery.shelf.recent_unlocks", empty_action: null },
      ],
    ],
    [
      "GET",
      /^\/api\/v1\/community\/discovery\/[^/]+$/,
      (url: URL) => ({
        key: url.pathname.split("/").pop(),
        label_key: "community:discovery.title",
        empty_action: null,
        state: "ok",
        items: [{ id: MASTER, display_name: "Alex", url: `/community/members/${MASTER}` }],
      }),
    ],
    ["GET", /^\/api\/v1\/community\/feed$/, { items: [], next_cursor: null }],
    // support
    [
      "GET",
      /^\/api\/v1\/me\/tickets$/,
      [
        {
          id: "00000000-0000-7000-8000-0000000000f1",
          number: 12,
          reference: "T-12",
          title: "Subtitles out of sync",
          state: "open",
          priority: "normal",
          type_key: "problem",
          assignee_id: null,
          incident_id: null,
          media_id: null,
          requester_id: MASTER,
          service_id: "s0",
          updated_at: at(-1),
        },
      ],
    ],
    [
      "GET",
      /^\/api\/v1\/tickets\/types$/,
      [{ key: "problem", label: "A problem", fields: [], public: true }],
    ],
    // the news and my feed
    [
      "GET",
      /^\/api\/v1\/news\/categories$/,
      [{ id: "cat-1", key: "portal", name: "The portal", enabled: true, position: 0, description: "" }],
    ],
    [
      "GET",
      /^\/api\/v1\/news\/featured$/,
      [newsCard("n-1", "The portal turns two"), newsCard("n-2", "New games in the library")],
    ],
    [
      "GET",
      /^\/api\/v1\/news$/,
      {
        items: [newsCard("n-1", "The portal turns two"), newsCard("n-3", "Maintenance on Sunday")],
        next_cursor: null,
      },
    ],
    [
      "GET",
      /^\/api\/v1\/me\/media\/feed$/,
      {
        follows: 1,
        seen_at: at(-2),
        items: [
          {
            at: at(-1),
            kind: "movie",
            object_id: MOVIE,
            title: "The Long Night",
            because: [{ kind: "genre", label: "Drama" }],
            image_id: null,
            unread: true,
            year: 2021,
          },
        ],
        upcoming: [
          {
            kind: "movie",
            tmdb_id: "123",
            title: "Next Winter",
            person: "Jane Doe",
            department: "Acting",
            role: "Lead",
            image_id: null,
            poster: null,
            object_id: null,
            rating: null,
            votes: 0,
            year: 2027,
            route: null,
            status: "missing",
          },
        ],
      },
    ],
    [
      "GET",
      /^\/api\/v1\/me\/media\/follows$/,
      { items: [{ kind: "genre", ref: "drama", label: "Drama", since: at(-30) }] },
    ],
    [
      "GET",
      /^\/api\/v1\/me\/news\/timeline$/,
      {
        total: 1,
        sources: [{ id: "src-1", kind: "rss", name: "Film news", since: at(-30) }],
        items: [
          {
            id: "item-1",
            title: "A festival opens",
            summary: "The festival opens tonight.",
            link: "https://example.org/festival",
            picture: null,
            published_at: at(-0.5),
            source: "Film news",
            source_id: "src-1",
            source_kind: "rss",
            category_id: null,
            hidden: false,
            pinned: false,
            mentions: [],
          },
        ],
      },
    ],
    // my privacy
    [
      "GET",
      /^\/api\/v1\/me\/privacy$/,
      {
        data: [
          {
            datum_class: "media.history",
            owner: "module:media",
            classification: "personal",
            description: "What I watched",
            retention_days: 365,
            default_level: "private",
            effective_level: "private",
            locked_by_policy: false,
            user_choosable: true,
          },
        ],
      },
    ],
    // the household (a master's view, or a profile's)
    ["GET", /^\/api\/v1\/household$/, household(profile)],
    [
      "GET",
      /^\/api\/v1\/household\/requests$/,
      [
        {
          id: "00000000-0000-7000-8000-0000000000c9",
          kind: "media",
          profile_id: PROFILE,
          profile_name: "Léa",
          subject_ref: MOVIE,
          title: "The Long Night",
          rating: "12",
          note: null,
          status: "pending",
          created_at: at(-0.2),
          decided_at: null,
          expires_at: null,
        },
      ],
    ],
    [
      "GET",
      /^\/api\/v1\/me\/media\/household$/,
      {
        days: 7,
        members: [MASTER, PROFILE].map((user_id) => ({
          user_id,
          minutes: 120,
          plays: 4,
          finished: 1,
          streak: 2,
          kinds: { movie: 80, game: 40 },
          series: [10, 20, 0, 30, 20, 25, 15],
          last: { at: at(-1), kind: "movie", title: "The Long Night", object_id: MOVIE },
          screen: null,
        })),
      },
    ],
    ["GET", /^\/api\/v1\/me\/media\/screen-time$/, screenTime],
  ];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    if (method !== "GET") posted.push(`${method} ${url.pathname}`);
    for (const [verb, path, answer] of handlers) {
      if (verb !== method && verb !== "*") continue;
      if (!path.test(url.pathname)) continue;
      const body = typeof answer === "function" ? await answer(url, route) : answer;
      if (isReply(body)) {
        if (body.raw !== undefined)
          return route.fulfill({
            status: body.status,
            contentType: body.contentType ?? "text/plain",
            body: body.raw,
          });
        if (body.body === undefined) return route.fulfill({ status: body.status });
        return route.fulfill({
          status: body.status,
          contentType: "application/json",
          body: JSON.stringify(body.body),
        });
      }
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    }
    if (!/\/(i18n|help)\b/.test(url.pathname)) unanswered.add(`${method} ${url.pathname}${url.search}`);
    return route.fallback();
  });
  return { ...portal, posted, unanswered, errors };
}

function newsCard(id: string, title: string) {
  return {
    id,
    slug: id,
    title,
    summary: "What changes, in a few words.",
    status: "published",
    category_id: "cat-1",
    published_at: at(-1),
    unread: false,
  };
}
