import type { Page } from "@playwright/test";

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
        w: 4,
        widget: entry?.widget,
      });
      dashboard.version += 1;
      return json(201, { layout_version: dashboard.version, id: null });
    }
    const instanceMatch = /^\/api\/v1\/dashboard\/widgets\/([^/]+)$/.exec(url.pathname);
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
      return json(200, { preferences: [] });
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
