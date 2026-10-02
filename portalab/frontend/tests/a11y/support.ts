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

export async function stubApi(
  page: Page,
  options: { failing?: string[] } = {},
): Promise<{ saved: Record<string, unknown> }> {
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
