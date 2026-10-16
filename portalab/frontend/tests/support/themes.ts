import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { ThemeDefinition } from "../../src/design-system/themes/schema";

/**
 * 028: every interface Portalab ships, as its packs hold them (``theme.json`` in each element) — the
 * interface's code bundles the socle's only; the tests still go over all of them.
 */
const PACKS = resolve(dirname(fileURLToPath(import.meta.url)), "../../../packs/builtin");
const FIRST = ["portalab-dark", "portalab-light", "orbit", "studio", "light", "dark", "high-contrast"];

const found: ThemeDefinition[] = readdirSync(PACKS).flatMap((pack) =>
  readdirSync(join(PACKS, pack, "elements")).flatMap((folder) => {
    const element = JSON.parse(readFileSync(join(PACKS, pack, "elements", folder, "element.json"), "utf8"));
    if (element.type !== "theme") return [];
    return [JSON.parse(readFileSync(join(PACKS, pack, "elements", folder, "theme.json"), "utf8"))];
  }),
);
const rank = (key: string) => (FIRST.includes(key) ? FIRST.indexOf(key) : FIRST.length);

export const BUILTIN_THEMES: readonly ThemeDefinition[] = found.sort(
  (a, b) => rank(a.key) - rank(b.key) || a.key.localeCompare(b.key),
);

export function builtinTheme(key: string): ThemeDefinition | undefined {
  return BUILTIN_THEMES.find((theme) => theme.key === key);
}
