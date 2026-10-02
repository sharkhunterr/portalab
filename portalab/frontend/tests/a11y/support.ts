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
