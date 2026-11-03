/**
 * The guided tours of the portal (#7): one per feature, each a few steps over the real pages. A step lights
 * the first of its ``targets`` that is shown (none: a centred bubble); ``route`` opens a page first;
 * ``click`` does the step's action for the member when they go on (enter the dashboard's edit mode, open a
 * request…) — they may also click the lit element themselves. A step whose element never shows is left
 * out, so a tour follows the theme's arrangement and what the member may see. Texts:
 * ``onboarding:tours.<tour>.title|description`` and ``onboarding:tours.<tour>.<step>.title|text``.
 */
export interface TourStep {
  key: string;
  icon: string;
  targets: readonly string[];
  route?: string;
  click?: boolean;
}

export type TourGroup = "start" | "media" | "play" | "help";

export interface TourDef {
  key: string;
  icon: string;
  group: TourGroup;
  /** Where it starts; the tour is offered only when this page is in the member's navigation. */
  route: string;
  steps: readonly TourStep[];
  /** The « first steps » mission it leads to, if any. */
  mission?: string;
  /** issue 181: offered only while this feature is there (the assistant switched on) */
  requires?: "assistant";
}

const done: TourStep = { key: "done", icon: "rocket", targets: [] };

/** Every navigation a theme may choose (sidebar, top bar, dock, orbit, launcher, terminal, console…). */
const NAVIGATION = [
  "[data-tour='nav']",
  ".shell-side",
  ".shell-topnav",
  ".shell-bottom-bar",
  ".shell-orbit__bubble",
  ".shell-launcher__start",
  ".shell-dock",
  ".shell-tabs",
  ".shell-terminal",
  ".shell-console",
  ".shell-reel",
  ".shell-lights",
  ".shell-vcr",
  ".shell-sheet",
  ".shell nav:not(main nav)",
];

export const TOURS: readonly TourDef[] = [
  {
    key: "portal",
    icon: "compass",
    group: "start",
    route: "/",
    mission: "discover_tour",
    steps: [
      { key: "progress", icon: "trophy", targets: [".shell-progress"] },
      { key: "search", icon: "search", targets: ["[data-tour='search']", ".header-search", ".shell-search"] },
      { key: "notifications", icon: "bell", targets: [".shell-bell", "[data-tour='notifications']"] },
      { key: "navigation", icon: "compass", targets: NAVIGATION },
      { key: "dashboard", icon: "dashboard", targets: [".widget-frame"] },
      { key: "customize", icon: "wand", targets: ["[data-tour='customize']"] },
      { key: "me", icon: "user", targets: [".shell-avatar-button", "[data-tour='nav']"] },
      { key: "done", icon: "rocket", targets: [] },
    ],
  },
  {
    key: "profile",
    icon: "user",
    group: "start",
    route: "/account",
    mission: "discover_profile",
    steps: [
      { key: "name", icon: "user", targets: ["#account-profile"] },
      { key: "avatar", icon: "image", targets: ["[data-tour='avatar']"] },
      { key: "themes", icon: "palette", route: "/settings/appearance", targets: [".theme-gallery__list"] },
      { key: "palettes", icon: "sparkles", targets: [".palettes"] },
      done,
    ],
  },
  {
    key: "dashboard",
    icon: "dashboard",
    group: "start",
    route: "/",
    mission: "discover_dashboard",
    steps: [
      { key: "edit", icon: "wand", targets: ["[data-tour='customize']"], click: true },
      { key: "add", icon: "plus", targets: ["[data-tour='add-widget']"] },
      { key: "widget", icon: "grip", targets: [".widget-frame__controls"] },
      { key: "screens", icon: "smartphone", targets: [".dashboard-toolbar"] },
      { key: "save", icon: "check", targets: ["[data-tour='dashboard-save']"] },
      done,
    ],
  },
  {
    // issue 344: the news — the team's headlines, then my feed: what comes, the sources, what I follow
    key: "news",
    icon: "newspaper",
    group: "start",
    route: "/news",
    steps: [
      { key: "featured", icon: "sparkles", targets: [".news-featured"] },
      { key: "channels", icon: "palette", targets: [".news-page fieldset.ds-subnav"] },
      { key: "latest", icon: "newspaper", targets: [".news-grid"] },
      { key: "upcoming", icon: "calendar", route: "/feed", targets: [".feed-list--rail"] },
      { key: "filters", icon: "rss", targets: [".feed-filters"] },
      { key: "stream", icon: "list", targets: [".feed-stream"] },
      { key: "follows", icon: "settings", targets: [".feed-manage"] },
      done,
    ],
  },
  {
    key: "media",
    icon: "film",
    group: "media",
    route: "/media",
    steps: [
      { key: "hero", icon: "sparkles", targets: [".media-hero"] },
      { key: "rows", icon: "film", targets: [".media-row"] },
      { key: "kinds", icon: "apps", targets: [".media-kinds"] },
      {
        key: "browse",
        icon: "search",
        route: "/media/browse",
        targets: [".catalog__search", ".catalog__kinds"],
      },
      { key: "card", icon: "play", targets: [".media-card"] },
      done,
    ],
  },
  {
    key: "request",
    icon: "inbox",
    group: "media",
    route: "/media/browse",
    mission: "discover_request",
    steps: [
      { key: "find", icon: "search", targets: [".catalog__search", ".catalog__kinds"] },
      { key: "search", icon: "search", targets: ["[data-tour='search']", ".header-search", ".shell-search"] },
      { key: "open", icon: "film", targets: [".media-card"] },
      done,
    ],
  },
  {
    key: "request_status",
    icon: "clock",
    group: "media",
    route: "/media/requests",
    mission: "discover_request_status",
    steps: [
      // issue 344: the figures are « My requests » in the Statistics section; the list is the section's page
      {
        key: "overview",
        icon: "chart",
        route: "/media/requests/stats",
        targets: [".requests-funnel", ".admin-stats"],
      },
      { key: "list", icon: "list", route: "/media/requests", targets: [".requests-row a"], click: true },
      { key: "journey", icon: "clock", targets: [".media-journey"] },
      { key: "badge", icon: "check", targets: [".media-badges"] },
      done,
    ],
  },
  {
    key: "stats",
    icon: "chart",
    group: "media",
    route: "/statistics",
    mission: "discover_stats",
    steps: [
      { key: "cards", icon: "chart", targets: [".stat-card"] },
      { key: "chart", icon: "trending", targets: [".stat-chart"] },
      { key: "gains", icon: "trophy", route: "/progression", targets: [".gain-sources"] },
      done,
    ],
  },
  {
    key: "progression",
    icon: "trophy",
    group: "play",
    route: "/progression",
    steps: [
      { key: "level", icon: "star", targets: [".gamification-hero", ".gamification-card"] },
      { key: "gains", icon: "trending", targets: [".gain-sources"] },
      { key: "achievements", icon: "medal", targets: [".achievements__head", ".achievements"] },
      { key: "leaderboard", icon: "crown", targets: [".leaderboard"] },
      done,
    ],
  },
  {
    // issue 344: today's games, their reminders, then the quests — filters, how many are done, time left
    key: "games",
    icon: "game",
    group: "play",
    route: "/games",
    steps: [
      { key: "today", icon: "calendar", targets: [".games-today"] },
      { key: "reminders", icon: "bell", targets: [".games-reminders"] },
      { key: "games", icon: "game", targets: [".games-grid"] },
      { key: "together", icon: "users", targets: [".games-together"] },
      { key: "quests", icon: "target", route: "/games/quests", targets: [".quest-summary"] },
      { key: "filters", icon: "list", targets: [".quest-board .ds-subnav"] },
      { key: "quest", icon: "clock", targets: [".quest-card"] },
      done,
    ],
  },
  {
    // issue 238: the media cards — my collection, my boosters, a set's binder, the shop's card boosters
    key: "cards",
    icon: "layers",
    group: "play",
    route: "/cards",
    steps: [
      { key: "stats", icon: "chart", targets: [".cards-summary"] },
      // issue 344: the boosters to open are a view of their own (« To open »), beside the collection
      { key: "views", icon: "library", targets: [".cards-views"] },
      { key: "search", icon: "search", targets: [".cards-search"] },
      { key: "sets", icon: "layers", targets: [".cards-sets a"], click: true },
      { key: "binder", icon: "star", targets: [".cards-binder"] },
      {
        key: "shop",
        icon: "shop",
        route: "/marketplace?type=card_booster",
        targets: [".vitrine-tile", ".vitrine-grid"],
      },
      done,
    ],
  },
  {
    key: "shop",
    icon: "shop",
    group: "play",
    route: "/marketplace",
    mission: "discover_shop",
    steps: [
      // issue 244: the showcase is the shop
      { key: "wallet", icon: "wallet", targets: [".vitrine-wallet"] },
      { key: "departments", icon: "store", targets: [".vitrine-nav"] },
      { key: "filters", icon: "search", targets: [".vitrine-search"] },
      { key: "featured", icon: "sparkles", targets: [".vitrine-spotlight"] },
      { key: "picks", icon: "flame", targets: [".vitrine-rail"] },
      { key: "product", icon: "gift", targets: [".vitrine-tile"] },
      { key: "coins", icon: "coins", targets: [".shell-progress__coins", ".shell-progress"] },
      done,
    ],
  },
  {
    // issue 344: what boosters and gifts left me — to open, waiting for my level, the card packs piled up
    key: "reserve",
    icon: "gift",
    group: "play",
    route: "/marketplace/reserve",
    steps: [
      { key: "jump", icon: "list", targets: [".reserve-jump"] },
      { key: "open", icon: "gift", targets: [".reserve-tiles"] },
      { key: "packs", icon: "layers", targets: [".reserve-rail"] },
      done,
    ],
  },
  {
    // issue 344: the community's projects — what they raised, one project, launching one's own
    key: "projects",
    icon: "target",
    group: "play",
    route: "/projects",
    steps: [
      { key: "figures", icon: "chart", targets: [".projects-figures"] },
      { key: "project", icon: "target", targets: [".project-card"] },
      { key: "launch", icon: "plus", targets: [".project-launch-cta"] },
      done,
    ],
  },
  {
    key: "community",
    icon: "users",
    group: "play",
    route: "/community",
    steps: [
      { key: "tabs", icon: "users", targets: [".hub-tabs"] },
      { key: "faces", icon: "smile", targets: [".community-faces"] },
      { key: "shelves", icon: "library", targets: [".community-shelf"] },
      done,
    ],
  },
  {
    key: "calendar",
    icon: "calendar",
    group: "play",
    route: "/calendar",
    steps: [
      { key: "month", icon: "calendar", targets: [".month-grid"] },
      { key: "day", icon: "clock", targets: [".month-grid__singles", ".month-grid__day"] },
      done,
    ],
  },
  {
    key: "ticket",
    icon: "lifebuoy",
    group: "help",
    route: "/support",
    mission: "discover_ticket",
    steps: [
      { key: "mine", icon: "inbox", targets: [".support-list", ".support-page"] },
      { key: "new", icon: "plus", targets: ["[data-tour='new-ticket']"], click: true },
      { key: "service", icon: "server", targets: [".service-picker"] },
      { key: "describe", icon: "message", targets: [".new-ticket .ds-field"] },
      { key: "diagnosis", icon: "lightbulb", targets: [".support-diagnosis"] },
      { key: "send", icon: "check", targets: ["[data-tour='ticket-submit']"] },
      done,
    ],
  },
  {
    // issue 181: the assistant — reached from any page, what it knows, how to ask, read and rate an answer
    key: "assistant",
    icon: "sparkles",
    group: "help",
    route: "/",
    mission: "discover_assistant",
    requires: "assistant",
    steps: [
      { key: "fab", icon: "sparkles", targets: [".ai-fab"], click: true },
      { key: "context", icon: "map-pin", targets: [".ai-context"] },
      { key: "ideas", icon: "lightbulb", targets: [".ai-ideas"] },
      { key: "ask", icon: "message", targets: [".ai-composer"] },
      { key: "sources", icon: "book-open", targets: [".ai-cards", ".ai-sources"] },
      { key: "rate", icon: "thumbs-up", targets: [".ai-bubble[data-role='assistant'] .ai-actions"] },
      { key: "usage", icon: "activity", targets: [".ai-usage"] },
      { key: "history", icon: "clock", targets: ["[data-tour='ai-history']"] },
      done,
    ],
  },
  {
    // issue 181: the assistant's capacities in the shop, and where its day's use shows
    key: "assistant_shop",
    icon: "zap",
    group: "play",
    route: "/marketplace",
    requires: "assistant",
    steps: [
      {
        key: "shelf",
        icon: "brain",
        route: "/marketplace?type=ai_capacity",
        targets: [".vitrine-grid", ".vitrine-tile"],
      },
      { key: "daily", icon: "zap", targets: [".vitrine-tile"] },
      { key: "coins", icon: "coins", targets: [".shell-progress__coins", ".shell-progress"] },
      { key: "fab", icon: "sparkles", targets: [".ai-fab"], click: true },
      { key: "usage", icon: "activity", targets: [".ai-usage"], click: true },
      { key: "details", icon: "info", targets: [".ai-usage__pop"] },
      done,
    ],
  },
  {
    key: "services",
    icon: "server",
    group: "help",
    route: "/services",
    steps: [
      { key: "status", icon: "heart", targets: [".services-status"] },
      { key: "card", icon: "server", targets: [".services-page__card"] },
      { key: "uptime", icon: "activity", targets: [".services-page__uptime"] },
      { key: "actions", icon: "link", targets: [".services-page__actions"] },
      { key: "header", icon: "alert", targets: [".shell-health"] },
      done,
    ],
  },
];

export function tourOf(key: string): TourDef | undefined {
  return TOURS.find((tour) => tour.key === key);
}

export function tourForMission(mission: string): TourDef | undefined {
  return TOURS.find((tour) => tour.mission === mission);
}
