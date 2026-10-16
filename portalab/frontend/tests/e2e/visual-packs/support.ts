import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { Page } from "@playwright/test";

/**
 * 028: what the e2e journeys of visual packs share — the sandbox page as the server serves it (its very
 * bootstrap, read from ``modules/visuals/sandbox.py``) and the files of an example pack, from disk.
 */
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");

export function sandboxDocument(): string {
  const source = readFileSync(resolve(ROOT, "backend/src/portalab/modules/visuals/sandbox.py"), "utf8");
  const bootstrap = /BOOTSTRAP = r"""([\s\S]*?)"""/.exec(source)?.[1] ?? "";
  return (
    '<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;height:100%;' +
    "background:transparent;overflow:hidden}#root{position:fixed;inset:0}</style></head>" +
    `<body><div id="root"></div><script>${bootstrap}</script></body></html>`
  );
}

/** Serves the sandbox and ``/api/v1/visuals/files/<pack>/<sha>/<path>`` from ``examples/visual-packs/<folder>``. */
export async function servePack(page: Page, folder: string): Promise<void> {
  await page.route("**/api/v1/visuals/sandbox", (route) =>
    route.fulfill({ status: 200, contentType: "text/html", body: sandboxDocument() }),
  );
  await page.route("**/api/v1/visuals/files/**", (route) => {
    const path = new URL(route.request().url()).pathname.split("/").slice(7).join("/");
    const file = resolve(ROOT, "examples/visual-packs", folder, "elements", path);
    const type = file.endsWith(".css") ? "text/css" : file.endsWith(".js") ? "text/javascript" : "text/plain";
    return route.fulfill({ status: 200, contentType: type, body: readFileSync(file, "utf8") });
  });
}

export function element(pack: string, folder: string, entry: Record<string, unknown>) {
  const base = `/api/v1/visuals/files/${pack}/0123456789abcdef/${folder}`;
  return {
    pack,
    sha: "0123456789abcdef",
    ...entry,
    file: entry.file ? `${base}/${entry.file}` : undefined,
    css: ((entry.css as string[] | undefined) ?? []).map((name) => `${base}/${name}`),
  };
}

/** The text a sandboxed script wrote, frame by frame (empty until it has drawn). */
export async function sandboxTexts(page: Page): Promise<string[]> {
  const texts: string[] = [];
  for (const frame of page.frames()) {
    if (!frame.url().includes("/visuals/sandbox")) continue;
    texts.push(await frame.evaluate(() => document.getElementById("root")?.innerText ?? "").catch(() => ""));
  }
  return texts;
}

/** A file of an example pack, read from disk (an interface's definition the server would list). */
export function packFile(folder: string, path: string): string {
  return readFileSync(resolve(ROOT, "examples/visual-packs", folder, "elements", path), "utf8");
}

/** The interface's real English words (the backend's catalogs), for journeys that read labels. */
export async function serveCatalogs(page: Page): Promise<void> {
  await page.route("**/api/v1/i18n/catalogs/**", (route) => {
    const namespace = new URL(route.request().url()).pathname.split("/").pop() ?? "";
    try {
      const messages = JSON.parse(
        readFileSync(resolve(ROOT, "backend/locales/en", `${namespace}.json`), "utf8"),
      );
      return route.fulfill({ json: { namespace, language: "en", messages } });
    } catch {
      return route.fulfill({ json: { namespace, language: "en", messages: {} } });
    }
  });
}
