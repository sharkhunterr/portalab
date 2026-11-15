import { readFileSync } from "node:fs";
import { expect, type Page, test } from "@playwright/test";
import { TOURS, type TourDef, type TourStep } from "../../../src/features/onboarding/tours";
import { becomeProfile, expectNoOverflow, signIn } from "../support/portal";
import { stubTourPortal } from "./fixtures";

// Issue 459 — every guided tour, at each release: started from the guide as a member does, walked to its end
// with « Next » (« Do it » where the step acts), on a desktop and on a phone. A tour whose element no longer
// shows loses that step silently in the runner — here it fails, the missing steps named.

const WIDTHS = {
  desktop: { width: 1440, height: 900 },
  phone: { width: 390, height: 844 },
} as const;

/**
 * Steps that legitimately cannot show at a width (``tour.step@width``) — each one justified. Keep it short.
 */
const LEFT_OUT: Record<string, string> = {
  // the filters' toggle is a narrow screen's: on a desktop the filters are always shown (catalog.css)
  "media.filters@desktop": "the filters are always open on a wide screen",
};

/**
 * Walks the app breaks today (``tour@width``), skipped until it is fixed — each with what was seen and where.
 */
const FIXME: Record<string, string> = {};

/**
 * What the member does at a step besides « Next », as the step invites them to: the assistant's sources and
 * rating are under an answer — there is one only once a question was asked.
 */
const MEMBER: Record<string, (page: Page) => Promise<void>> = {
  "assistant.ask": async (page) => {
    await page.locator(".ai-composer textarea").fill("Is Media up?");
    await page.locator(".ai-composer textarea").press("Enter");
    await expect(page.locator(".ai-bubble[data-role='assistant'] .ai-cards")).toBeVisible();
  },
};

// the English catalog the portal falls back on (the stub serves no catalog)
const en = JSON.parse(
  readFileSync(new URL("../../../../backend/locales/en/onboarding.json", import.meta.url), "utf8"),
) as Record<string, string>;
const label = (key: string) => en[key] ?? key;

/** The step shown, once the bubble kept it a moment (a step being left out flashes for one frame at most). */
async function settledStep(page: Page, previous: number): Promise<number | null> {
  const handle = await page.waitForFunction(
    (before) => {
      const w = window as unknown as { __tourText?: string; __tourSince?: number };
      const tour = document.querySelector(".tour");
      if (!tour) return "gone";
      const text = document.querySelector(".tour__bubble .tour__count")?.textContent ?? "";
      const ready = tour.getAttribute("data-ready") === "true";
      const now = performance.now();
      if (text !== w.__tourText) {
        w.__tourText = text;
        w.__tourSince = now;
        return false;
      }
      const index = Number(/(\d+)\s*\/\s*\d+\s*$/.exec(text)?.[1] ?? 0);
      return ready && index !== before && now - (w.__tourSince ?? now) > 400 ? String(index) : false;
    },
    previous,
    { polling: 50, timeout: 60_000 },
  );
  const value = (await handle.jsonValue()) as string;
  return value === "gone" ? null : Number(value);
}

async function startFromGuide(page: Page, tour: TourDef) {
  await page.goto("/guide");
  const title = label(`tours.${tour.key}.title`);
  const button =
    tour.key === "portal"
      ? page.locator(".guide-hero").getByRole("button", { name: label("guide.start") })
      : page.getByRole("button", { name: `${label("guide.start")} : ${title}` });
  await expect(button, `the guide offers « ${title} »`).toBeVisible({ timeout: 15_000 });
  await button.click();
}

for (const [width, viewport] of Object.entries(WIDTHS)) {
  test.describe(`${width}`, () => {
    test.use({ viewport, hasTouch: width === "phone" });

    for (const tour of TOURS) {
      test(`the ${tour.key} tour walks to its end`, async ({ page }) => {
        const broken = FIXME[`${tour.key}@${width}`];
        test.fixme(broken !== undefined, broken);
        test.setTimeout(240_000);
        const { posted, saved, unanswered, errors } = await stubTourPortal(page);
        await signIn(page);
        await startFromGuide(page, tour);
        const shown: number[] = [];
        let index = 0;
        for (;;) {
          const step = await settledStep(page, index);
          if (step === null) break;
          index = step;
          shown.push(step);
          const def = tour.steps[step - 1] as TourStep;
          const where = `${tour.key}.${def.key}@${width}`;
          const bubble = page.locator(".tour__bubble");
          // the bubble within the screen, the element lit, the page no wider than the screen
          const box = await bubble.boundingBox();
          expect.soft(box, `${where}: the bubble is shown`).not.toBeNull();
          if (box) {
            expect.soft(box.x, `${where}: the bubble's left edge`).toBeGreaterThanOrEqual(0);
            expect.soft(box.y, `${where}: the bubble's top edge`).toBeGreaterThanOrEqual(0);
            expect
              .soft(box.x + box.width, `${where}: the bubble's right edge`)
              .toBeLessThanOrEqual(viewport.width);
            expect
              .soft(box.y + box.height, `${where}: the bubble's bottom edge`)
              .toBeLessThanOrEqual(viewport.height);
          }
          if (def.targets.length)
            await expect
              .soft(page.locator(".tour__spot"), `${where}: an element is lit`)
              .not.toHaveAttribute("data-empty", "true");
          await expectNoOverflow(page, where);
          await MEMBER[`${tour.key}.${def.key}`]?.(page);
          const last = step === tour.steps.length;
          const action = last ? label("tour.finish") : def.click ? label("tour.doIt") : label("next");
          const primary = bubble.locator(".tour__actions button").last();
          await expect(primary, `${where}: its button`).toHaveText(action);
          await primary.click();
        }
        const missing = tour.steps
          .filter((s, i) => !shown.includes(i + 1) && !LEFT_OUT[`${tour.key}.${s.key}@${width}`])
          .map((s) => s.key);
        if (missing.length || errors.length)
          console.log(
            `${tour.key}@${width}\n errors:\n  ${errors.join("\n  ")}\n unanswered:\n  ${[...unanswered].join("\n  ")}`,
          );
        expect(missing, `${tour.key}@${width}: the steps left out`).toEqual([]);
        // the end is said once: the tour is marked seen and its completion is sent
        await expect.poll(() => posted).toContain(`POST /api/v1/me/onboarding/tours/${tour.key}/complete`);
        await expect
          .poll(() => saved["shell.onboarding.toursSeen"] as string[] | undefined)
          .toContain(tour.key);
      });
    }
  });
}

test("a household profile is not offered the tours of what it cannot use", async ({ page }) => {
  await stubTourPortal(page, { profile: true });
  await signIn(page);
  await becomeProfile(page);
  await page.goto("/guide");
  await expect(page.getByRole("heading", { name: label("guide.title") })).toBeVisible();
  await expect(page.getByRole("heading", { name: label("tours.media.title") })).toBeVisible();
  for (const key of ["request", "request_status", "retro", "household"])
    await expect(page.getByRole("heading", { name: label(`tours.${key}.title`) })).toHaveCount(0);
});

// issue 459: over the assistant's window (a modal one, which hides everything else from assistive
// technologies), the tour's bubble stays readable — a screen reader reads the step and reaches « Next »
test("the bubble stays readable over the assistant's window", async ({ page }) => {
  await stubTourPortal(page);
  await signIn(page);
  await startFromGuide(page, TOURS.find((tour) => tour.key === "assistant") as TourDef);
  await page
    .getByRole("dialog", { name: label("tours.assistant.fab.title") })
    .getByRole("button", { name: label("tour.doIt") })
    .click();
  await expect(page.getByRole("dialog", { name: label("tours.assistant.context.title") })).toBeVisible();
});
