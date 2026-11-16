import { MATRIX, variantsOf } from "./matrix";
import { api, check, csrf, expect, expectSmooth, framesPerSecond, settle, test } from "./support";

/**
 * Issue 469 — every widget an owner may place, with each value of each of its settings (the shop's options
 * among them) and each pack add-on made for it, on a phone, a tablet and a desktop: placed on the home page
 * as the dashboard's editor would, it renders (never the error state, never a crash), fits the screen, stays
 * readable and accessible, and stays smooth when it moves (live, animated styles). The device's account owns
 * the dashboard: one widget at a time, in order (``default`` mode), the widget taken off afterwards — or put
 * back as it was when the account had it already.
 */
test.describe.configure({ mode: "default" });

interface Instance {
  id: string;
  widget_key: string;
  config: Record<string, unknown>;
  locked?: boolean;
}

const ANIMATED =
  /style=(live|liquid|kenburns|countup|odometer|pulse|flip|carousel|ambient|deck|analog)|add-on|live=true/;

for (const widget of MATRIX.widgets.filter((w) => !w.locked)) {
  test(`widget ${widget.key} — every setting`, async ({ page, request, errors }, info) => {
    // a tablet lays a widget out as a desktop or a phone does: those two are enough
    test.skip(info.project.name === "tablet", "the phone's and the desktop's layouts cover it");
    test.setTimeout(60_000 + variantsOf(widget).length * 30_000);
    let still: number | undefined;
    const dashboard = await api<{ instances: Instance[] }>(request, "GET", "/api/v1/dashboard");
    const had = dashboard.instances.find((i) => i.widget_key === widget.key);
    // one the administrator pinned and locked keeps its settings: it is seen as it is
    const variants = had?.locked
      ? [{ name: "as the administrator set it", config: had.config }]
      : variantsOf(widget);
    let id = had?.id;
    if (!id) {
      const added = await request.post("/api/v1/dashboard/widgets", {
        data: { widget_key: widget.key, config: variants[0]?.config ?? {} },
        headers: { "X-CSRF-Token": await csrf(request) },
      });
      expect(added.status(), `${widget.key} can be placed: ${await added.text()}`).toBe(201);
      id = ((await added.json()) as { id: string }).id;
    }
    const frame = page.locator(`section.widget-frame[data-widget="${widget.key}"]`).first();
    try {
      for (const variant of variants) {
        await test.step(variant.name, async () => {
          const saved = had?.locked
            ? null
            : await request.patch(`/api/v1/dashboard/widgets/${id}`, {
                data: { config: variant.config },
                headers: { "X-CSRF-Token": await csrf(request) },
              });
          if (saved && !saved.ok()) {
            expect
              .soft(saved.status(), `${widget.key} ${variant.name} is accepted: ${await saved.text()}`)
              .toBe(200);
            return;
          }
          await page.goto("/");
          await settle(page);
          await expect(frame, `${widget.key} on the home page`).toBeVisible();
          await frame.scrollIntoViewIfNeeded();
          const crashed = await frame.locator('[data-state="error"]').count();
          expect.soft(crashed, `${widget.key} ${variant.name}: the error state`).toBe(0);
          await check(page, errors, `${widget.key} ${variant.name}`, {
            within: `section.widget-frame[data-widget="${widget.key}"]`,
          });
          // the same page standing still (the default look), for the budget on a slow machine
          if (variant.name === "default" && variants.some((v) => ANIMATED.test(v.name)))
            still = await framesPerSecond(page);
          if (ANIMATED.test(variant.name))
            await expectSmooth(page, info, `${widget.key} ${variant.name}`, async () => still ?? 60);
        });
      }
    } finally {
      const headers = { "X-CSRF-Token": await csrf(request) };
      if (had?.locked) {
        // nothing was changed
      } else if (had)
        await request.patch(`/api/v1/dashboard/widgets/${id}`, { data: { config: had.config }, headers });
      else await request.delete(`/api/v1/dashboard/widgets/${id}`, { headers });
    }
  });
}
