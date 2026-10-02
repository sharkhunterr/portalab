import type { Page } from "@playwright/test";

/** Minimal API stub for journeys: an account that can sign in, with its permissions and preferences. */
export async function stubApi(page: Page): Promise<{ saved: Record<string, unknown> }> {
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
