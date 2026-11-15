import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { crumbKey } from "../../../src/shell/breadcrumbs/Breadcrumbs";

// issue 456: a route's crumb is written in English in the routes and read from the shell's catalog — one
// missing showed « Accueil / Mon foyer / My household » on a French page
const here = dirname(fileURLToPath(import.meta.url));
const routes = readFileSync(resolve(here, "../../../src/shell/router/routes.tsx"), "utf8");
const crumbs = [...new Set([...routes.matchAll(/crumb:\s*"([^"]+)"/g)].map((m) => m[1] as string))];

describe("the routes' crumbs", () => {
  it.each(["en", "fr"])("each has its words in the %s catalog", (language) => {
    const catalog = JSON.parse(
      readFileSync(resolve(here, `../../../../backend/locales/${language}/shell.json`), "utf8"),
    ) as Record<string, string>;
    expect(crumbs.length).toBeGreaterThan(20);
    expect(crumbs.filter((text) => !catalog[`crumb.${crumbKey(text)}`])).toEqual([]);
  });
});
