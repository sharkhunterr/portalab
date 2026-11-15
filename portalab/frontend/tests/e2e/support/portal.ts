import { expect, type Page } from "@playwright/test";
import { NAVIGATION, stubApi } from "../../a11y/support";

/**
 * Issues 438–453 — the portal of the latest features, stubbed for the journeys: households (made or not,
 * a common pot or separate profiles), a household profile signed in, the welcome, the administration's
 * pages (site identity, gamification, the setup assistant). Routes registered here win over ``stubApi``'s.
 */
export const MASTER = "00000000-0000-7000-8000-000000000001";
export const PROFILE = "00000000-0000-7000-8000-0000000000c1";

export interface PortalOptions {
  admin?: boolean;
  profile?: boolean; // signed in as a household profile of MASTER
  made?: boolean; // the master's household is made
  economy?: "pot" | "dispatch";
  welcome?: boolean; // the welcome opens by itself
}

const json = (body: unknown, status = 200) => ({
  status,
  contentType: "application/json",
  body: JSON.stringify(body),
});

function section(key: string, icon: string, entries: Array<[string, string, string]>, audience = "everyone") {
  return {
    key,
    label_key: `nav.section.${key}`,
    icon,
    audience,
    direct: entries.length === 1,
    topics: [],
    entries: entries.map(([entry, label, route]) => ({ key: entry, label_key: label, icon, route })),
  };
}

export async function stubPortal(page: Page, options: PortalOptions = {}) {
  const state = {
    made: options.made ?? true,
    economy: options.economy ?? "pot",
    profiles: [] as Array<{ id: string; display_name: string; kind: string }>,
    pins: [] as unknown[],
  };
  const { saved } = await stubApi(page);
  if (options.welcome) {
    await page.route("**/api/v1/me/onboarding/welcome", (route) =>
      route.fulfill(json({ enabled: true, message: "" })),
    );
  }
  await page.route("**/api/v1/me/permissions", (route) =>
    route.fulfill(
      json({
        permissions: ["users.self.manage", "media.read", ...(options.admin ? ["configuration.manage"] : [])],
        roles: options.admin ? ["admin"] : ["user"],
      }),
    ),
  );
  await page.route("**/api/v1/me/navigation", (route) => {
    const sections = [
      ...NAVIGATION.sections,
      ...(state.made || options.profile
        ? [section("household", "users", [["shell.household", "nav.household", "/household"]])]
        : []),
      ...(options.admin
        ? [
            section(
              "admin",
              "settings",
              [
                ["shell.admin.site", "nav.admin.site", "/admin/site"],
                ["shell.admin.gamification", "nav.admin.gamification", "/admin/gamification"],
              ],
              "administration",
            ),
          ]
        : []),
    ];
    return route.fulfill(json({ ...NAVIGATION, sections }));
  });
  await page.route("**/api/v1/i18n/languages", (route) =>
    route.fulfill(
      json({
        default: "en",
        items: [
          { code: "en", name_native: "English", name_en: "English", direction: "ltr" },
          { code: "fr", name_native: "Français", name_en: "French", direction: "ltr" },
        ],
      }),
    ),
  );
  const members = () => [
    {
      id: MASTER,
      display_name: "Alex",
      kind: "owner",
      color: "#6366f1",
      has_avatar: false,
      has_pin: false,
      progress: { xp: 120, level: 2, coins: 40, contribution: 3 },
      community_visible: true,
    },
    ...state.profiles.map((p) => ({
      ...p,
      color: "#ec4899",
      has_avatar: false,
      has_pin: false,
      progress: { xp: 0, level: 1, coins: 0, contribution: 0 },
      community_visible: false,
      restrictions: { max_age: 12, allow_unrated: false, blocked: [], mode: "hide", requests: true },
    })),
  ];
  await page.route("**/api/v1/household**", async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    const path = url.pathname;
    if (path === "/api/v1/household/session")
      return route.fulfill(
        json({
          enabled: true,
          made: state.made || Boolean(options.profile),
          owner_id: MASTER,
          active_id: options.profile ? PROFILE : MASTER,
          must_choose: false,
          members: [],
        }),
      );
    if (path === "/api/v1/household/made" && method === "POST") {
      state.made = true;
      return route.fulfill({ status: 204 });
    }
    if (path === "/api/v1/household/economy" && method === "PUT") {
      state.economy = (route.request().postDataJSON() as { economy: "pot" | "dispatch" }).economy;
      return route.fulfill({ status: 204 });
    }
    if (path === "/api/v1/household/profiles" && method === "POST") {
      const body = route.request().postDataJSON() as { display_name: string; kind: string };
      const id = `00000000-0000-7000-8000-0000000001${String(state.profiles.length).padStart(2, "0")}`;
      state.profiles.push({ id, display_name: body.display_name, kind: body.kind });
      return route.fulfill(json({ id }, 201));
    }
    if (path.startsWith("/api/v1/household/members/") && method === "PUT") {
      state.pins.push(route.request().postDataJSON());
      return route.fulfill({ status: 204 });
    }
    if (path === "/api/v1/household/requests") return route.fulfill(json([]));
    if (path === "/api/v1/household")
      return route.fulfill(
        json({
          enabled: true,
          owner_id: MASTER,
          me: options.profile ? PROFILE : MASTER,
          can_manage: !options.profile,
          max_profiles: 8,
          palette: ["#6366f1", "#ec4899"],
          totals: { xp: 120, level: 2, coins: 40, contribution: 3 },
          members: options.profile
            ? [
                ...members(),
                {
                  id: PROFILE,
                  display_name: "Léa",
                  kind: "child",
                  color: "#ec4899",
                  has_avatar: false,
                  has_pin: false,
                  progress: { xp: 10, level: 1, coins: 5, contribution: 0 },
                  community_visible: false,
                },
              ]
            : members(),
          economy: state.economy,
        }),
      );
    return route.fulfill(json({ items: [] }));
  });
  await page.route("**/api/v1/me/media/links", (route) => route.fulfill(json([])));
  await page.route("**/api/v1/retro/accounts", (route) => route.fulfill(json([])));
  await page.route("**/api/v1/me/notification-preferences", (route) =>
    route.fulfill(
      json({
        digest: "off",
        categories: [
          {
            key: "media.available",
            label_key: "notifications:category.media",
            user_mutable: true,
            channels: {
              portal: { enabled: true, mandatory: false, locked: false },
              email: { enabled: false, mandatory: false, locked: false },
            },
          },
        ],
      }),
    ),
  );
  await page.route("**/api/v1/admin/config", (route) =>
    route.fulfill(
      json({
        settings: [
          { key: "i18n.systemLanguage", value: "fr-FR", source: "global", description: "", sensitive: false },
          { key: "i18n.defaultLocale", value: "fr-FR", source: "global", description: "", sensitive: false },
          { key: "i18n.defaultLanguage", value: "fr", source: "global", description: "", sensitive: false },
          { key: "household.maxProfiles", value: 8, source: "default", description: "", sensitive: false },
        ],
      }),
    ),
  );
  await page.route("**/api/v1/admin/site", (route) =>
    route.fulfill(
      json({
        name: "Starport",
        default_name: "Portalab",
        tagline: {},
        currency: {},
        currency_short: "XC",
        currency_icon: "",
        logo: null,
        icon: null,
      }),
    ),
  );
  await page.route("**/api/v1/admin/gamification/household", (route) =>
    route.fulfill(json({ grouped: true })),
  );
  return { state, saved };
}

/** The household profile chosen (after signing in, as the real switch does): the portal reloads as it. */
export async function becomeProfile(page: Page) {
  await page.route("**/api/v1/me", (route) =>
    route.fulfill(
      json({
        id: PROFILE,
        login: "lea",
        display_name: "Léa",
        email: null,
        has_avatar: false,
        state: "active",
        created_at: "2026-10-01T00:00:00Z",
        deletion_due_at: null,
        profile_of: MASTER,
      }),
    ),
  );
  await page.goto("/");
}

export async function signIn(page: Page) {
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("banner")).toBeVisible();
}

/** Nothing wider than the screen: the page never slides sideways (the widest culprits named). */
export async function expectNoOverflow(page: Page, where: string) {
  // a toast sliding in, a screen appearing: measured once their (finite) animations are over
  await page
    .waitForFunction(
      () =>
        document
          .getAnimations()
          .every(
            (a) => a.playState !== "running" || a.effect?.getTiming().iterations === Number.POSITIVE_INFINITY,
          ),
      undefined,
      { timeout: 3000 },
    )
    .catch(() => undefined);
  const report = await page.evaluate(() => {
    const extra = document.documentElement.scrollWidth - window.innerWidth;
    // inside a strip that scrolls (or clips) sideways on purpose — tabs, carousels — is not the page's width
    // ...nor what cannot be seen (a toast leaving, faded out before it is taken away)
    const contained = (el: Element) => {
      for (let up: Element | null = el; up && up !== document.body; up = up.parentElement) {
        const style = getComputedStyle(up);
        if (style.opacity === "0" || style.visibility === "hidden") return true;
        if (up !== el && style.overflowX !== "visible") return true;
      }
      return false;
    };
    const wide = [...document.querySelectorAll("body *")]
      .filter((el) => {
        const box = el.getBoundingClientRect();
        return box.width > 0 && box.right > window.innerWidth + 1 && !contained(el);
      })
      .slice(0, 5)
      .map((el) => `${el.tagName.toLowerCase()}.${String(el.className).split(" ")[0]}`);
    return { extra: Math.max(0, extra), wide };
  });
  expect(report, `${where} fits the screen: ${JSON.stringify(report)}`).toEqual({ extra: 0, wide: [] });
}
