import { expect, type Page } from "@playwright/test";
import { builtinTheme } from "../support/themes";

/**
 * The header's search (027): a field that answers while one types — on a phone, the magnifier that opens it.
 */
export function headerSearch(page: Page) {
  const banner = page.getByRole("banner");
  return banner
    .getByRole("combobox", { name: "Search" })
    .or(banner.getByRole("button", { name: "Search" }))
    .first();
}

/** Issue 171: the assistant's round button, on every page (« Ask the assistant »). */
export const ASSISTANT = /assistant/i;

/**
 * The personal menu (027): the avatar in the header — or, on a phone whose header keeps the essentials and
 * puts the menu in a panel, the profile card of that panel with the personal pages and « Sign out ».
 */
export async function expectPersonalMenu(page: Page) {
  const banner = page.getByRole("banner");
  const avatar = banner.getByRole("button", { name: /Personal menu/ });
  const panel = banner.getByRole("button", { name: "Open navigation" });
  await expect(avatar.or(panel).first()).toBeVisible();
  if (await avatar.isVisible()) return;
  await panel.click();
  const drawer = page.getByRole("dialog", { name: "Main navigation" });
  await expect(drawer.getByRole("button", { name: "Sign out" })).toBeVisible();
  await expect(drawer.getByRole("link", { name: "Appearance" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
}

/**
 * 028: the interfaces beyond the socle's five are their packs' — the server's catalog serves them, as here
 * (``GET /api/v1/ui/themes`` items: key, name, family, definition).
 */
export function themeCatalog(keys: readonly string[]) {
  return keys.flatMap((key) => {
    const definition = builtinTheme(key);
    if (!definition) return [];
    const { name, family, colorScheme } = definition as unknown as {
      name: string;
      family?: string;
      colorScheme?: string;
    };
    return [{ key, name, family: family ?? null, colorScheme, definition, version: 1 }];
  });
}

/** Minimal API stub for journeys: an account that can sign in, with its permissions and preferences. */
export const NAVIGATION = {
  version: "v1",
  degraded: false,
  groups: [
    {
      key: "main",
      label_key: "nav.group.main",
      entries: [
        { key: "shell.home", label_key: "nav.home", route: "/" },
        { key: "health.services", label_key: "nav.services", route: "/services" },
      ],
    },
    {
      key: "me",
      label_key: "nav.group.me",
      entries: [
        { key: "identity.account", label_key: "nav.account", route: "/account" },
        { key: "ui.appearance", label_key: "nav.appearance", route: "/settings/appearance" },
      ],
    },
  ],
  // 027: the server's section view (the 004 ``groups`` above stay as the deprecated alias)
  sections: [
    {
      key: "home",
      label_key: "nav.section.home",
      icon: "home",
      audience: "everyone",
      direct: true,
      topics: [],
      entries: [{ key: "shell.home", label_key: "nav.home", icon: "home", route: "/" }],
    },
    {
      key: "services",
      label_key: "nav.section.services",
      icon: "server",
      audience: "everyone",
      direct: true,
      topics: [],
      entries: [{ key: "health.services", label_key: "nav.services", icon: "server", route: "/services" }],
    },
  ],
  personal: [
    { key: "identity.account", label_key: "nav.account", icon: "user", route: "/account" },
    { key: "ui.appearance", label_key: "nav.appearance", icon: "palette", route: "/settings/appearance" },
  ],
  commands: [
    { key: "health.services", label_key: "nav.services", route: "/services", kind: "navigate" },
    { key: "identity.account", label_key: "nav.account", route: "/account", kind: "navigate" },
    { key: "ui.appearance", label_key: "nav.appearance", route: "/settings/appearance", kind: "navigate" },
    {
      key: "shell.shortcuts_help",
      label_key: "nav.shortcuts",
      kind: "action",
      action_id: "shell.show_shortcuts",
    },
  ],
  related: {},
  crumbs: {},
};

/** A server-side dashboard shared by every page/context of a test (persistence across devices). */
export interface DashboardStore {
  version: number;
  instances: Array<Record<string, unknown>>;
  /** Arrangements saved by the editor (027), in order. */
  arrangements?: Array<Array<{ id: string; x: number; y: number; w: number; h: number }>>;
}

const WIDGET_META = (title: string, extra: Record<string, unknown> = {}) => ({
  title_key: title,
  description_key: null,
  icon: null,
  component_id: null,
  template: "stat",
  refresh_mode: "on_view",
  refresh_interval_s: null,
  min_w: 2,
  min_h: 1,
  max_w: 12,
  max_h: 4,
  multiple: false,
  config_schema: { type: "object", properties: {} },
  ...extra,
});

export const CATALOG = [
  { key: "t.weather", placed: false, widget: WIDGET_META("Weather") },
  { key: "t.notes", placed: false, widget: WIDGET_META("Notes") },
];

export function newDashboard(): DashboardStore {
  const make = (key: string, title: string, position: number) => ({
    id: `00000000-0000-7000-8000-00000000000${position + 1}`,
    widget_key: key,
    status: "active",
    position,
    x: (position % 2) * 6,
    y: Math.floor(position / 2) * 2,
    w: 6,
    h: 2,
    config: {},
    policy: "free",
    locked: false,
    mandatory: false,
    removable: true,
    hideable: true,
    available: true,
    widget: WIDGET_META(title),
  });
  return {
    version: 1,
    instances: [make("t.welcome", "Welcome", 0), make("t.services", "Services status", 1)],
  };
}

function reorder(store: DashboardStore, id: string, position: number) {
  const items = [...store.instances].sort((a, b) => Number(a.position) - Number(b.position));
  const index = items.findIndex((i) => i.id === id);
  const [item] = items.splice(index, 1);
  if (item) items.splice(Math.max(0, Math.min(position, items.length)), 0, item);
  items.forEach((i, n) => {
    i.position = n;
  });
  store.instances = items;
}

export async function stubApi(
  page: Page,
  options: { failing?: string[]; dashboard?: DashboardStore } = {},
): Promise<{ saved: Record<string, unknown> }> {
  const dashboard = options.dashboard ?? newDashboard();
  let signedIn = false;
  const saved: Record<string, unknown> = {};
  const me = {
    id: "00000000-0000-7000-8000-000000000001",
    login: "alex",
    display_name: "Alex",
    email: null,
    has_avatar: false,
    state: "active",
    created_at: "2026-10-01T00:00:00Z",
    deletion_due_at: null,
  };
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    const json = (status: number, body: unknown) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (url.pathname === "/api/v1/auth/login" && method === "POST") {
      signedIn = true;
      return json(200, {
        csrf_token: "csrf",
        display_name: "Alex",
        expires_at: "2027-01-01T00:00:00Z",
        user_id: me.id,
      });
    }
    if (!signedIn) return json(401, { code: "auth.unauthenticated", title: "Unauthorized", status: 401 });
    if (url.pathname === "/api/v1/me") return json(200, me);
    if (url.pathname === "/api/v1/me/permissions")
      return json(200, { permissions: ["users.self.manage"], roles: ["user"] });
    if (url.pathname === "/api/v1/me/navigation") return json(200, NAVIGATION);
    if (url.pathname === "/api/v1/me/progression")
      return json(200, {
        user_id: me.id,
        xp: 240,
        level: 3,
        level_floor: 200,
        next_level_at: 400,
        contribution: 0,
        coins: 120,
        reserved_coins: 0,
        achievements: 1,
      });
    if (url.pathname === "/api/v1/me/notifications/unread-count") return json(200, { unread: 2 });
    // issue 171: an assistant answers — its round button is on every page
    if (url.pathname === "/api/v1/ai/status")
      return json(200, {
        available: true,
        provider_state: "ok",
        auto_navigate: false,
        name: "",
        daily_budget: 0,
        used_today: 0,
        recharge: 0,
        perks: {},
        shop: false,
        ideas: [],
      });
    if (url.pathname === "/api/v1/services/health") {
      const failing = options.failing ?? [];
      return json(200, {
        items: ["Media", "Books", "Music"].map((name, index) => ({
          id: `s${index}`,
          name,
          connector: "fake",
          state: failing.includes(name) ? "unavailable" : "operational",
          availability: 1,
        })),
      });
    }
    if (url.pathname === "/api/v1/dashboard")
      return json(200, { layout_version: dashboard.version, instances: dashboard.instances });
    if (url.pathname === "/api/v1/dashboard/catalog")
      return json(
        200,
        CATALOG.map((c) => ({
          ...c,
          placed: dashboard.instances.some((i) => i.widget_key === c.key && i.status === "active"),
        })),
      );
    if (url.pathname === "/api/v1/dashboard/since-last-login")
      return json(200, { since: "2026-10-01T00:00:00Z", items: [], unavailable: [] });
    if (url.pathname === "/api/v1/dashboard/widgets" && method === "POST") {
      const key = String((route.request().postDataJSON() as { widget_key: string }).widget_key);
      const entry = CATALOG.find((c) => c.key === key);
      dashboard.instances.push({
        ...(dashboard.instances[0] as Record<string, unknown>),
        id: `00000000-0000-7000-8000-0000000000${10 + dashboard.instances.length}`,
        widget_key: key,
        position: dashboard.instances.length,
        // like the server: the first free row below the others (027)
        x: 0,
        y: Math.max(0, ...dashboard.instances.map((i) => Number(i.y) + Number(i.h))),
        w: 4,
        widget: entry?.widget,
      });
      dashboard.version += 1;
      return json(201, { layout_version: dashboard.version, id: null });
    }
    if (url.pathname === "/api/v1/dashboard/arrangement" && method === "PUT") {
      // 027: the editor's Save — store the coordinates as sent (the client already resolved them)
      const body = route.request().postDataJSON() as {
        items: Array<{ id: string; x: number; y: number; w: number; h: number }>;
      };
      for (const item of body.items) {
        const stored = dashboard.instances.find((i) => i.id === item.id);
        if (stored) Object.assign(stored, { x: item.x, y: item.y, w: item.w, h: item.h });
      }
      dashboard.arrangements = [...(dashboard.arrangements ?? []), body.items];
      dashboard.version += 1;
      return json(200, { layout_version: dashboard.version });
    }
    const instanceMatch = /^\/api\/v1\/dashboard\/widgets\/([^/]+)$/.exec(url.pathname);
    if (instanceMatch && method === "DELETE") {
      // 027: « Remove » takes the widget off the dashboard (its configuration goes with it)
      dashboard.instances = dashboard.instances.filter((i) => i.id !== instanceMatch[1]);
      dashboard.version += 1;
      return json(200, { layout_version: dashboard.version });
    }
    if (instanceMatch && method === "PATCH") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      const item = dashboard.instances.find((i) => i.id === instanceMatch[1]);
      if (item) {
        if (typeof body.position === "number") reorder(dashboard, String(item.id), body.position);
        for (const field of ["w", "h", "status"]) if (body[field] !== undefined) item[field] = body[field];
      }
      dashboard.version += 1;
      return json(200, { layout_version: dashboard.version, id: instanceMatch[1] });
    }
    if (/^\/api\/v1\/widgets\/[^/]+\/data$/.test(url.pathname))
      return json(200, {
        state: "available",
        as_of: null,
        stale_after_s: null,
        data: { value: 7, label: "items" },
        partial_reasons: [],
        config_invalid: false,
      });
    if (url.pathname === "/api/v1/palette/resolve") {
      const route = url.searchParams.get("route") ?? "/";
      const q = url.searchParams.get("q") ?? "";
      return json(200, {
        destinations: [],
        actions: route.startsWith("/services")
          ? [
              {
                id: "health.restart",
                label: "Restart service",
                kind: "navigate",
                route: "/services",
                action_id: null,
                sensitivity: "destructive",
                confirmation_required: true,
                keywords: ["restart"],
              },
            ]
          : [],
        object: q === "#42" ? { kind: "services", id: "s1", title: "Media", route: "/services" } : null,
        intent: null,
        suggestions: [],
        assistant: "unavailable",
      });
    }
    if (url.pathname === "/api/v1/search/suggest") {
      const q = (url.searchParams.get("q") ?? "").toLowerCase();
      return json(200, {
        items: "media".startsWith(q)
          ? [{ kind: "services", id: "s0", title: "Media server", url_ref: "/services" }]
          : [],
      });
    }
    if (url.pathname === "/api/v1/search" && method === "POST") {
      const q = String((route.request().postDataJSON() as { q?: string }).q ?? "");
      return json(200, {
        request_id: "r",
        took_ms: 1,
        semantic: "unavailable",
        total: 1,
        groups: [
          {
            kind: "services",
            label_key: "search.kind.services",
            state: "ok",
            next_cursor: null,
            facets: [],
            items: [
              {
                kind: "services",
                id: "s0",
                title: `Media server (${q})`,
                url_ref: "/services",
                snippet: [
                  { text: "Media", hit: true },
                  { text: " server", hit: false },
                ],
                language: null,
                matched_by: "exact",
                score: 1,
                facets: {},
              },
            ],
          },
        ],
      });
    }
    if (url.pathname === "/api/v1/me/search-history") return json(200, []);
    if (url.pathname === "/api/v1/me/preferences") {
      if (method === "PUT") Object.assign(saved, route.request().postDataJSON());
      // what was saved comes back, as the server keeps it (a reload keeps the chosen theme)
      return json(200, { preferences: Object.entries(saved).map(([key, value]) => ({ key, value })) });
    }
    if (url.pathname === "/api/v1/ui/themes") {
      return json(200, {
        themes: [],
        policy: {
          allowedThemes: ["light", "dark", "high-contrast"],
          defaultTheme: "light",
          textScaleMin: 0.85,
          textScaleMax: 2,
          forceReducedMotion: false,
        },
      });
    }
    return json(200, { items: [] });
  });
  return { saved };
}
