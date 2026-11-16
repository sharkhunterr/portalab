import { resolve } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { type APIRequestContext, test as base, expect, type Page, type TestInfo } from "@playwright/test";
import { AUTH } from "./global-setup";

/**
 * Issue 469 — what the nightly journeys share: the accounts (one per device owning every product, a member
 * owning none), the looks worn in the page only (the account's saved preferences stay as they are), and the
 * checks every page passes whatever the interface — interfaces rename the pages (their vocabulary) and move the navigation
 * (a dock, a launcher, a terminal, a VCR…), so nothing here reads a label: pages are reached by their address
 * and the navigation by the links' targets.
 */

/** A signed-in account's session: a device's own (``phone``, ``tablet``, ``desktop``) or ``member``. */
export function as(who: string) {
  return resolve(AUTH, `${who}.json`);
}

/**
 * The test: signed in as its device's account (``asMember`` for the one owning nothing), the console's errors
 * and the page's crashes gathered (checked by ``check``), and the interface it wears (``wear``) only in its own
 * page — the account's saved preferences shared by the tests running beside it stay as they are.
 */
export const test = base.extend<{ errors: string[]; asMember: boolean; wear: Record<string, unknown> }>({
  asMember: [false, { option: true }],
  wear: [{}, { option: true }],
  storageState: async ({ asMember }, use, info) => {
    await use(as(asMember ? "member" : info.project.name));
  },
  page: async ({ page, wear }, use) => {
    await page.route("**/api/v1/me/preferences", async (route) => {
      if (route.request().method() !== "GET" || !Object.keys(wear).length) return route.fallback();
      try {
        const answer = await route.fetch();
        const body = (await answer.json()) as { preferences: Array<{ key: string; value: unknown }> };
        const kept = body.preferences.filter((p) => !(p.key in wear));
        const worn = Object.entries(wear).map(([key, value]) => ({
          key,
          value,
          source: "user",
          locked: false,
        }));
        await route.fulfill({ response: answer, json: { ...body, preferences: [...kept, ...worn] } });
      } catch {
        // the page left before the answer came (a navigation): nothing waits for it any more
      }
    });
    await use(page);
  },
  errors: async ({ page }, use) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(`crash: ${error.message.split("\n")[0]}`));
    page.on("console", (message) => {
      if (message.type() !== "error") return;
      const text = message.text();
      // an outside service not connected on this portal answers 503/404: the page says so, it is not a fault
      if (/Failed to load resource|status of (4\d\d|503)/.test(text)) return;
      errors.push(`console: ${text.split("\n")[0]?.slice(0, 240)}`);
    });
    await use(errors);
  },
});
export { expect };

export async function csrf(request: APIRequestContext): Promise<string> {
  const state = await request.storageState();
  return (
    state.cookies.find((c) => c.name === "portalab_csrf" || c.name === "__Host-portalab_csrf")?.value ?? ""
  );
}

export async function api<T>(
  request: APIRequestContext,
  method: string,
  path: string,
  data?: unknown,
): Promise<T> {
  const answer = await request.fetch(path, {
    method,
    data,
    headers: { "X-CSRF-Token": await csrf(request) },
  });
  expect(answer.ok(), `${method} ${path}: ${answer.status()} ${(await answer.text()).slice(0, 300)}`).toBe(
    true,
  );
  const text = await answer.text();
  return (text ? JSON.parse(text) : null) as T;
}

/**
 * The page shown and settled: its main content there, its data arrived (no region still loading — the live
 * stream keeps the network busy for good, so « network idle » never comes), its fonts drawn, its finite
 * animations over.
 */
export async function settle(page: Page) {
  await expect(page.locator("#main-content")).toBeVisible({ timeout: 30_000 });
  await page.waitForLoadState("load").catch(() => undefined);
  await page
    .waitForFunction(
      () =>
        !document.querySelector('.shell [aria-busy="true"], .shell [data-state="loading"]') &&
        document.fonts.status === "loaded",
      undefined,
      { timeout: 15_000, polling: 100 },
    )
    .catch(() => undefined);
  await page
    .waitForFunction(
      () =>
        document
          .getAnimations()
          .every(
            (a) => a.playState !== "running" || a.effect?.getTiming().iterations === Number.POSITIVE_INFINITY,
          ),
      undefined,
      { timeout: 4000 },
    )
    .catch(() => undefined);
}

/** What a member would see wrong on this page, whatever the interface: each problem as one line. */
export interface CheckOptions {
  /** false: no axe pass; « touch »: the touch targets only (the colors were read on the desktop already) */
  axe?: boolean | "touch";
  /** axe on this part only (a widget's frame) */
  within?: string;
}

export async function problemsOf(page: Page, errors: string[], options: CheckOptions = {}) {
  // read standing still: a carousel fading, a glow pulsing would be measured half-way (« reduce motion » stops
  // them, as it does for the members who ask for it); smoothness is measured with the motion on
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.waitForTimeout(300);
  try {
    return await findProblems(page, errors, options);
  } finally {
    await page.emulateMedia({ reducedMotion: "no-preference" });
  }
}

async function findProblems(page: Page, errors: string[], options: CheckOptions) {
  const problems: string[] = [...errors.splice(0)];
  // 1. it renders: a heading (the interface may rename it, never remove it), no crashed region
  const layout = await page.evaluate(() => {
    const out: string[] = [];
    const main = document.getElementById("main-content");
    if (!main?.querySelector("h1, h2")) out.push("no heading in the page");
    // 2. it fits the screen: nothing wider than it outside a strip that scrolls (or clips) on purpose
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
      .slice(0, 3)
      .map((el) => `${el.tagName.toLowerCase()}.${String(el.className).split(" ")[0]}`);
    const extra = document.documentElement.scrollWidth - window.innerWidth;
    if (extra > 1 || wide.length)
      out.push(`wider than the screen by ${Math.max(0, extra)} px: ${wide.join(", ")}`);
    // 3. it stays readable: a label cut off without an ellipsis (a button, a link, a heading, a tab)
    const clipped = [...document.querySelectorAll("button, a, h1, h2, h3, [role=tab], label, th")]
      .filter((el) => {
        const node = el as HTMLElement;
        if (!node.offsetParent || !node.innerText.trim() || node.closest('[aria-hidden="true"]'))
          return false;
        // shortened on purpose further in (a name with its « … »): not cut off
        if (
          [...node.querySelectorAll("*")].some((child) => getComputedStyle(child).textOverflow === "ellipsis")
        )
          return false;
        const style = getComputedStyle(node);
        if (style.textOverflow === "ellipsis" || style.overflowX === "visible") return false;
        if (style.overflowX === "auto" || style.overflowX === "scroll") return false;
        return node.scrollWidth > node.clientWidth + 2 && node.clientWidth > 2; // (not one hidden for the eye)
      })
      .slice(0, 3)
      .map((el) => `«${(el as HTMLElement).innerText.trim().slice(0, 40)}» (${el.tagName.toLowerCase()})`);
    if (clipped.length) out.push(`text cut off: ${clipped.join(", ")}`);
    return out;
  });
  problems.push(...layout);
  // 4. accessible, contrast included (WCAG 2.2 AA)
  if (options.axe !== false) {
    let builder = new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
      .exclude("iframe")
      // an interface drawn in miniature (aria-hidden, its « Aa » a font sample): a picture, its letters
      // incidental (WCAG 1.4.3) — faded on purpose when not the one chosen
      .exclude(".theme-mini");
    if (options.within) builder = builder.include(options.within);
    if (options.axe === "touch") builder = builder.withRules(["target-size"]);
    const results = await builder.analyze();
    for (const violation of results.violations)
      problems.push(
        `axe ${violation.id} ×${violation.nodes.length}: ${violation.nodes
          .slice(0, 2)
          .map((n) => n.target.join(" "))
          .join(" | ")}`,
      );
  }
  return problems;
}

/** Each page's problems told apart in the report (``expect.soft``: every page of the journey is seen). */
export async function check(page: Page, errors: string[], where: string, options: CheckOptions = {}) {
  const problems = await problemsOf(page, errors, options);
  expect.soft(problems, `${where} (${page.url()})`).toEqual([]);
  return problems;
}

/**
 * The smoothness budget, calibrated on the runner's kind of machine (no graphics card: the page is drawn by the
 * processor): at least 12 frames a second drawn as it is — or, on a machine already slower than that (a busy
 * runner), half of what the same page draws without the motion — and, the processor slowed 4× (a modest
 * phone), no task holding the page longer than 250 ms, no more than a second held in 2.5 s. The heavy ones
 * measured fall far beyond (4–10 frames, 1.2–2.3 s held), the others well within (16–60 frames).
 */
export const SMOOTH = { fps: 12, longest: 250, blocked: 1000, span: 2500 };

export interface Smoothness {
  /** frames a second, as it is (the drawing's cost) */
  fps: number;
  /** the processor slowed 4×: the longest task and the time held past 50 ms per task (the script's cost) */
  longest: number;
  blocked: number;
}

/** Frames a second the page draws, left alone for ``ms``. */
export async function framesPerSecond(page: Page, ms = SMOOTH.span): Promise<number> {
  return page.evaluate(async (span) => {
    let frames = 0;
    const start = performance.now();
    await new Promise<void>((done) => {
      const tick = () => {
        frames += 1;
        if (performance.now() - start < span) requestAnimationFrame(tick);
        else done();
      };
      requestAnimationFrame(tick);
    });
    return (frames * 1000) / (performance.now() - start);
  }, ms);
}

/** The page left alone (its ambient, its live widgets): its frames as it is, then its tasks slowed 4×. */
export async function smoothness(page: Page, ms = SMOOTH.span): Promise<Smoothness> {
  const fps = await framesPerSecond(page, ms);
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  const tasks = await page.evaluate(async (span) => {
    let longest = 0;
    let blocked = 0;
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        longest = Math.max(longest, entry.duration);
        blocked += Math.max(0, entry.duration - 50);
      }
    });
    try {
      observer.observe({ type: "longtask" });
    } catch {
      // no long task API: nothing held is seen
    }
    await new Promise((done) => setTimeout(done, span));
    observer.disconnect();
    return { longest, blocked };
  }, ms);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
  await cdp.detach();
  return { fps, ...tasks };
}

export function fpsBudget(still?: number): number {
  return still ? Math.min(SMOOTH.fps, 0.5 * still) : SMOOTH.fps;
}

/**
 * The page stays smooth (``expect.soft``). ``still`` draws the same page without its motion — asked only when
 * the frames fall short, to tell a heavy animation from a slow machine.
 */
export async function expectSmooth(page: Page, info: TestInfo, label: string, still?: () => Promise<number>) {
  const measure = await smoothness(page);
  let budget = SMOOTH.fps;
  if (measure.fps < budget && still) budget = fpsBudget(await still());
  note(
    info,
    "smoothness",
    `${label}: ${measure.fps.toFixed(0)} fps (budget ${budget.toFixed(0)}), slowed 4×: longest task ${measure.longest.toFixed(0)} ms, ${measure.blocked.toFixed(0)} ms held`,
  );
  expect.soft(measure.fps, `${label}: frames per second`).toBeGreaterThanOrEqual(budget);
  expect
    .soft(measure.longest, `${label}: longest task (ms), processor slowed 4×`)
    .toBeLessThan(SMOOTH.longest);
  expect
    .soft(measure.blocked, `${label}: time held (ms in 2.5 s), processor slowed 4×`)
    .toBeLessThan(SMOOTH.blocked);
  return measure;
}

/** The same page without its ambient (the motion behind it), for ``expectSmooth``: worn again afterwards. */
export function withoutAmbient(page: Page, wear: Record<string, unknown>) {
  return async () => {
    const had = "ui.ambient" in wear;
    const worn = wear["ui.ambient"];
    wear["ui.ambient"] = "none";
    try {
      await page.reload();
      await settle(page);
      return await framesPerSecond(page);
    } finally {
      if (had) wear["ui.ambient"] = worn;
      else delete wear["ui.ambient"];
      await page.reload();
      await settle(page);
    }
  };
}

export function note(info: TestInfo, type: string, description: string) {
  info.annotations.push({ type, description });
}

/**
 * The navigation, whatever its shape: from the home page, reach ``route`` through what lies outside the page's
 * content — a link to it at once, else the openers (a section, a start button, a bubble, a menu…) one after
 * the other, two levels deep. True when the page opened.
 */
export async function reachByNavigation(page: Page, route: string): Promise<boolean> {
  const link = page.locator(`a[href="${route}"]:not(#main-content a):visible`).first();
  // (a dropdown — the personal menu — is not the navigation, and it holds every click outside it while open)
  const openers = () =>
    page.locator(
      ':is(button, [role="button"])[aria-expanded="false"]:not([aria-haspopup="menu"]):not(#main-content *):visible',
    );
  const go = async () => {
    if (!(await link.count())) return false;
    await link.click();
    await page.waitForURL((url) => url.pathname === route, { timeout: 5000 }).catch(() => undefined);
    return new URL(page.url()).pathname === route;
  };
  if (await go()) return true;
  // a level down, inside the window a navigation opened, its buttons too: a folder of the sheet opens in
  // place (a drill-down, no « expanded » state) — never the one closing it or going back. Read again before
  // each try, by their rank: leaving a folder draws its tiles anew
  const inside = () =>
    page
      .locator('[role="dialog"] button:visible:not([aria-label*="close" i]):not([aria-label*="back" i])')
      .filter({
        hasNotText: /^\s*(close|back)\s*$/i,
      });
  const tryLevel = async (depth: number): Promise<boolean> => {
    // the openers as they stand when a level starts (one opened leaves the « closed » list: no index shifts)
    const handles = (await openers().elementHandles()).slice(0, 16);
    const folders = depth ? Math.min(await inside().count(), 16) : 0;
    const tries = [
      ...handles.map((handle) => async () => ((await handle.isVisible().catch(() => false)) ? handle : null)),
      ...Array.from({ length: folders }, (_, i) => async () => {
        const button = inside().nth(i);
        return (await button.count()) ? button : null;
      }),
    ];
    for (const next of tries) {
      const opener = await next();
      if (!opener) continue;
      const before = await openers().count();
      await opener.click({ timeout: 3000 }).catch(() => undefined);
      await page.waitForTimeout(250); // a sheet sliding in, a list unfolding
      if (await go()) return true;
      if (depth < 1 && (await openers().count()) !== before && (await tryLevel(depth + 1))) return true;
      if (depth > 0) {
        // a folder opened in place is left by its « back »; otherwise the next section replaces this one
        const back = page.locator('[role="dialog"] button:visible').filter({ hasText: /back/i });
        if (await back.count())
          await back
            .first()
            .click({ timeout: 2000 })
            .catch(() => undefined);
      } else {
        await page.keyboard.press("Escape"); // at the top, what it opened is shut
        await page.waitForTimeout(150);
      }
    }
    return false;
  };
  return tryLevel(0);
}
