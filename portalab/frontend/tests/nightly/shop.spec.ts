import { MATRIX } from "./matrix";
import { api, check, csrf, expect, expectSmooth, settle, test, withoutAmbient } from "./support";

/**
 * Issue 469 — the shop's other products, on the real catalog: what an owner gets and a member owning nothing
 * does not (widget options, widgets, statistics — the server's word, then the page's), the catalog's own
 * consistency (an option sold names a widget, one of its settings and one of its values), and every look worn:
 * each palette over the home page (contrast), each ambient (it renders, it stays smooth), each notification
 * style and animation, level-up and celebration (no crash), each profile design on the member's profile.
 */

const desktopOnly = (name: string) => test.skip(name !== "desktop", "once is enough: not a matter of screen");

test.describe("what the shop locks", () => {
  test("shop — an owner has every option and widget, a member none", async ({ request }, info) => {
    desktopOnly(info.project.name);
    const owned = await api<{ locked: string[] }>(request, "GET", "/api/v1/dashboard/locked-options");
    expect(owned.locked, "options still locked for an owner of everything").toEqual([]);
    const catalog = await api<Array<{ key: string; locked: boolean }>>(
      request,
      "GET",
      "/api/v1/dashboard/catalog",
    );
    expect(
      catalog.filter((w) => w.locked).map((w) => w.key),
      "widgets still in the shop for an owner",
    ).toEqual([]);
    expect(MATRIX.locked.length, "options locked for a member owning nothing").toBeGreaterThan(0);
  });

  test("shop — each option sold names a widget, one of its settings and one of its values", async ({
    request: _,
  }, info) => {
    desktopOnly(info.project.name);
    const broken: string[] = [];
    for (const option of MATRIX.locked) {
      const [widget, setting = ""] = option.split(":");
      const [field = "", value = ""] = setting.split("=");
      const entry = MATRIX.widgets.find((w) => w.key === widget);
      if (!entry) {
        broken.push(`${option}: no such widget`);
        continue;
      }
      if (field === "_options") {
        if (!MATRIX.addons.some((a) => a.look === value && (!a.for || a.for === widget)))
          broken.push(`${option}: no such add-on for it`);
        continue;
      }
      const schema = entry.widget.config_schema.properties?.[field];
      if (!schema) broken.push(`${option}: the widget has no « ${field} » setting`);
      else if (schema.enum && !schema.enum.map(String).includes(value))
        broken.push(`${option}: « ${value} » is not one of ${schema.enum.join(", ")}`);
    }
    expect(broken).toEqual([]);
  });

  test.describe(() => {
    test.use({ asMember: true });
    test("shop — a member owning nothing is refused each option sold", async ({ request }, info) => {
      desktopOnly(info.project.name);
      const locked = await api<{ locked: string[] }>(request, "GET", "/api/v1/dashboard/locked-options");
      expect(locked.locked.sort()).toEqual([...MATRIX.locked].sort());
      const dashboard = await api<{ instances: Array<{ id: string; widget_key: string }> }>(
        request,
        "GET",
        "/api/v1/dashboard",
      );
      const accepted: string[] = [];
      for (const option of MATRIX.locked) {
        const [widget = "", setting = ""] = option.split(":");
        const [field = "", value = ""] = setting.split("=");
        const placed = dashboard.instances.find((i) => i.widget_key === widget);
        let id = placed?.id;
        const headers = { "X-CSRF-Token": await csrf(request) };
        if (!id) {
          const added = await request.post("/api/v1/dashboard/widgets", {
            data: { widget_key: widget },
            headers,
          });
          if (!added.ok()) continue; // the widget itself is sold: placing it is refused already
          id = ((await added.json()) as { id: string }).id;
        }
        const config = field === "_options" ? { _options: [value] } : { [field]: value };
        const saved = await request.patch(`/api/v1/dashboard/widgets/${id}`, { data: { config }, headers });
        if (saved.ok()) accepted.push(option);
        if (!placed) await request.delete(`/api/v1/dashboard/widgets/${id}`, { headers });
      }
      expect(accepted, "sold options a member owning nothing could put on").toEqual([]);
    });

    test("shop — a member owning nothing has the statistics locked", async ({
      request,
      page,
      errors,
    }, info) => {
      desktopOnly(info.project.name);
      const locked = await api<{ locked: string[] }>(request, "GET", "/api/v1/me/media/insights/locked");
      expect(locked.locked.length, "statistics sold, locked for a member owning nothing").toBeGreaterThan(0);
      const history = await request.get("/api/v1/media/insights?period=all");
      if (locked.locked.includes("media.insights.history")) {
        expect(history.status(), "the long history, refused").toBe(403);
        expect(((await history.json()) as { code: string }).code).toBe("media.statistic_locked");
      }
      await page.goto("/media/insights");
      await settle(page);
      await check(page, errors, "statistics, locked");
    });
  });

  test("shop — an owner has every statistic", async ({ request, page, errors }, info) => {
    desktopOnly(info.project.name);
    const locked = await api<{ locked: string[] }>(request, "GET", "/api/v1/me/media/insights/locked");
    expect(locked.locked, "statistics still locked for an owner of everything").toEqual([]);
    const history = await request.get("/api/v1/media/insights?period=all");
    expect(history.status(), "the long history, open").not.toBe(403);
    await page.goto("/media/insights");
    await settle(page);
    await expect(page.locator(".insights-locked")).toHaveCount(0);
    await check(page, errors, "statistics, unlocked");
  });
});

/** Looks worn as preferences (the appearance page's choices): the type of the pack element → its key. */
const WORN: Record<string, string> = {
  palette: "ui.palette",
  ambient: "ui.ambient",
  notification_style: "ui.notificationStyle",
  notification_animation: "ui.notificationAnimation",
  level_up: "ui.levelUp",
  effect: "ui.celebration",
};

for (const [type, preference] of Object.entries(WORN)) {
  for (const look of MATRIX.looks[type] ?? []) {
    test.describe(() => {
      test.use({ wear: { [preference]: look } });
      test(`look ${type} ${look}`, async ({ page, errors, wear }, info) => {
        // palettes change every color (contrast on every device), ambients move (smoothness on a phone and a
        // desktop); the rest only shows on an event: once, on the desktop
        const everywhere = type === "palette" || (type === "ambient" && info.project.name !== "tablet");
        if (!everywhere) desktopOnly(info.project.name);
        await page.goto("/");
        await settle(page);
        await check(page, errors, `${type} ${look}`, { axe: type === "palette" });
        if (type === "ambient") {
          await expectSmooth(page, info, `ambient ${look}`, withoutAmbient(page, wear));
        }
      });
    });
  }
}

/** The profile's designs (``PUT /me/profile-looks``): each one the catalog offers, worn and shown. */
const LISTED: Record<string, string> = {
  banner: "banners",
  frame: "frames",
  background: "backgrounds",
  name: "names",
  level: "levels",
  title: "titles",
  badges: "badges",
};

test.describe("profile designs", () => {
  // each slot is worn apart from the others: the slots go side by side, one design at a time in each

  for (const slot of Object.keys(LISTED)) {
    test(`look profile ${slot} — every design`, async ({ page, request, errors }, info) => {
      desktopOnly(info.project.name);
      test.setTimeout(20 * 60_000);
      const me = await api<{ id: string }>(request, "GET", "/api/v1/me");
      const catalog = await api<Record<string, unknown>>(request, "GET", "/api/v1/me/profile-looks");
      const choices = designsOf(catalog, slot);
      expect(choices.length, `designs offered for « ${slot} »`).toBeGreaterThan(0);
      for (const choice of choices) {
        const value = slot === "badges" ? [choice] : choice;
        const worn = await request.put("/api/v1/me/profile-looks", {
          data: { slot, value },
          headers: { "X-CSRF-Token": await csrf(request) },
        });
        if (!worn.ok()) {
          expect.soft(worn.status(), `${slot} ${choice} can be worn: ${await worn.text()}`).toBe(200);
          continue;
        }
        await page.goto(`/community/members/${me.id}`);
        await settle(page);
        await check(page, errors, `${slot} ${choice}`, { axe: false });
      }
      await request.put("/api/v1/me/profile-looks", {
        data: { slot, value: null },
        headers: { "X-CSRF-Token": await csrf(request) },
      });
    });
  }
});

/** The designs the catalog lists for a slot (``GET /me/profile-looks``: ``banners``, ``frames``…), « none » aside. */
function designsOf(catalog: Record<string, unknown>, slot: string): string[] {
  const list = catalog[LISTED[slot] ?? slot];
  return (
    (Array.isArray(list) ? list : [])
      // one still locked for an owner of everything is not on sale now (out of season, withdrawn): not given
      .filter((item) => (item as { locked?: boolean })?.locked !== true)
      .map((item) => (item as { key?: string })?.key)
      .filter((key): key is string => typeof key === "string" && key !== "none")
  );
}
