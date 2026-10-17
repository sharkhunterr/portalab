import { createHash } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

/**
 * 028 (T094, SC-004): the isolation of a pack's script — each probe of ``tests/fixtures/visual-probes`` attempts
 * one capability a pack must never have (the portal's cookies, the browser's storage, any request, the page
 * around it, moving that page, a popup, a form) inside the very sandbox the portal serves: its document and
 * its content security policy read from ``modules/visuals/sandbox.py``, framed with ``sandbox="allow-scripts"``
 * only, as the interface does. Every probe must report « refused », no request may leave the sandbox, and the
 * page around it never moves.
 */
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "../../../..");
const PROBES = resolve(HERE, "../../fixtures/visual-probes");
const SOURCE = readFileSync(resolve(ROOT, "backend/src/portalab/modules/visuals/sandbox.py"), "utf8");
const BOOTSTRAP = /BOOTSTRAP = r"""([\s\S]*?)"""/.exec(SOURCE)?.[1] ?? "";
const HASH = createHash("sha256").update(BOOTSTRAP).digest("base64");
// the policy as the server sends it: its literals joined, the bootstrap's hash in place
const POLICY = [...(/POLICY = \(([\s\S]*?)\n\)/.exec(SOURCE)?.[1] ?? "").matchAll(/f?"([^"]*)"/g)]
  .map((m) => m[1])
  .join("")
  .replace("{_HASH}", HASH);
const DOCUMENT =
  '<!doctype html><html><head><meta charset="utf-8"></head>' +
  `<body><div id="root"></div><script>${BOOTSTRAP}</script></body></html>`;

const HOST = `<!doctype html><html><body><script>
  window.reports = [];
  window.addEventListener("message", (event) => {
    const data = event.data || {};
    if (data.type === "navigate" && String(data.key).startsWith("probe:")) window.reports.push(JSON.parse(String(data.key).slice(6)));
  });
  window.runProbe = (source) => {
    const frame = document.createElement("iframe");
    frame.setAttribute("sandbox", "allow-scripts");
    frame.src = "/sandbox";
    window.addEventListener("message", (event) => {
      if (event.source === frame.contentWindow && event.data && event.data.type === "loaded")
        frame.contentWindow.postMessage({ type: "run", source, element: {}, context: {} }, "*");
    });
    document.body.append(frame);
  };
</script></body></html>`;

const probes = readdirSync(PROBES).filter((name) => name.endsWith(".js"));

test("the policy read is the one the portal serves", () => {
  expect(POLICY).toContain("connect-src 'none'");
  expect(POLICY).toContain(`script-src 'sha256-${HASH}' blob:`);
});

for (const probe of probes) {
  test(`a pack's script may not reach ${probe.replace(".js", "")}`, async ({ page }) => {
    const escaped: string[] = [];
    await page.route("http://portal.test/**", (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/") return route.fulfill({ status: 200, contentType: "text/html", body: HOST });
      if (path === "/sandbox")
        return route.fulfill({
          status: 200,
          contentType: "text/html",
          headers: { "Content-Security-Policy": POLICY, "X-Frame-Options": "SAMEORIGIN" },
          body: DOCUMENT,
        });
      escaped.push(`${route.request().method()} ${path}`); // anything else left the sandbox
      return route.fulfill({ status: 404, body: "" });
    });
    await page.context().addCookies([{ name: "session", value: "member", url: "http://portal.test/" }]);
    await page.goto("http://portal.test/");
    const popups: string[] = [];
    page.context().on("page", (opened) => popups.push(opened.url()));
    await page.evaluate(
      (source) => (window as unknown as { runProbe: (s: string) => void }).runProbe(source),
      readFileSync(resolve(PROBES, probe), "utf8"),
    );
    await expect
      .poll(() => page.evaluate(() => (window as unknown as { reports: unknown[] }).reports.length), {
        timeout: 10_000,
      })
      .toBe(1);
    const [report] = await page.evaluate(
      () => (window as unknown as { reports: Array<{ probe: string; refused: boolean }> }).reports,
    );
    await page.waitForTimeout(500); // what it may have started (a navigation, a form) has had time to happen
    expect(new URL(page.url()).pathname).toBe("/"); // the page around it never moved
    expect(popups).toEqual([]);
    expect(escaped).toEqual([]);
    // the moves of the page and the forms are judged by what happened, not by what the script believed
    if (report?.probe !== "navigation" && report?.probe !== "form") expect(report?.refused).toBe(true);
  });
}
