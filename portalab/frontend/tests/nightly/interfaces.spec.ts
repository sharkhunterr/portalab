import { BUILTIN_THEMES } from "../support/themes";
import { api, check, expect, expectSmooth, reachByNavigation, settle, test, withoutAmbient } from "./support";

/**
 * Issue 469 — every interface Portalab ships (each pack's ``theme.json``, the socle's included), on a phone, a
 * tablet and a desktop (the projects), worn by a member who owns it: the pages that show the most of an
 * interface (the home page and its widgets, the shop, the statistics, the community, the news, the settings)
 * each render, fit the screen, stay readable and accessible; every section of the member's navigation can be
 * reached through the interface's own navigation, whatever its shape; the home page stays smooth.
 */
const PAGES = ["/", "/marketplace", "/media/insights", "/community", "/news", "/settings"];

interface NavSection {
  key: string;
  entries: Array<{ route: string }>;
}

for (const theme of BUILTIN_THEMES) {
  test.describe(() => {
    test.use({ wear: { "ui.theme": theme.key } });
    test(`interface ${theme.key} — pages, navigation, smoothness`, async ({
      page,
      request,
      errors,
      wear,
    }, info) => {
      test.setTimeout(8 * 60_000); // a cosmos navigation (planisphere, station) has many doors to try
      const served = await api<{ themes: Array<{ key: string }> }>(request, "GET", "/api/v1/ui/themes");
      expect(
        served.themes.map((t) => t.key),
        "the portal serves this interface",
      ).toContain(theme.key);

      for (const path of PAGES) {
        await test.step(`page ${path}`, async () => {
          await page.goto(path);
          await settle(page);
          await expect(page.locator("html")).toHaveAttribute("data-theme", theme.key);
          // the colors are the interface's whatever the screen: read in full on the desktop (and the phone's
          // home page); the phone and the tablet check what their layout changes — the touch targets
          const device = info.project.name;
          const full = device === "desktop" || (device === "phone" && path === "/");
          await check(page, errors, `${theme.key} ${path}`, { axe: full ? true : "touch" });
        });
      }

      await test.step("navigation", async () => {
        const navigation = await api<{ sections: NavSection[]; personal: Array<{ route: string }> }>(
          request,
          "GET",
          "/api/v1/me/navigation",
        );
        const unreachable: string[] = [];
        for (const section of navigation.sections) {
          const route = section.entries[0]?.route;
          if (!route) continue;
          await page.goto(route === "/" ? "/settings" : "/");
          await settle(page);
          if (!(await reachByNavigation(page, route))) unreachable.push(`${section.key} (${route})`);
        }
        expect.soft(unreachable, `${theme.key}: sections the navigation cannot reach`).toEqual([]);
      });

      await test.step("smoothness", async () => {
        if (info.project.name === "tablet") return; // a phone's and a desktop's processors bound it
        await page.goto("/");
        await settle(page);
        await expectSmooth(page, info, theme.key, withoutAmbient(page, wear));
      });
    });
  });
}
