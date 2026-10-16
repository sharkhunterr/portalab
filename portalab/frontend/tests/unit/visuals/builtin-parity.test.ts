import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import postcss from "postcss";
import { describe, expect, it } from "vitest";
import { lookSelectorOk, splitSelectors } from "../../../src/design-system/visuals/cssGuard";

// 028 B2 (T033): Portalab's own looks live in their packs — each look a built-in pack holds (the socle's
// fallbacks apart) is drawn by its element's own stylesheet, none is left in the application's stylesheets,
// and every rule of those stylesheets passes the guard an imported pack's would.

const APP = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
const PACKS = join(APP, "packs", "builtin");
const THEMES = join(APP, "frontend", "src", "design-system", "themes");
const SHEETS = ["cosmetics", "levelup", "ambient", "celebration", "universe"];
const HOOKS: Record<string, RegExp> = {
  avatar_frame: /\.avatar-frame\[data-frame="([^"]+)"\]/g,
  level_badge: /\.ds-level\[data-look="([^"]+)"\]/g,
  profile_banner: /\.profile-banner\[data-banner="([^"]+)"\]/g,
  name_style: /\.name-style\[data-name="([^"]+)"\]/g,
  title: /\.cosmetic-title\[data-style="([^"]+)"\]/g,
  badge: /\.cosmetic-badge\[data-style="([^"]+)"\]/g,
  level_up: /\.levelup\[data-look="([^"]+)"\]/g,
  ambient: /\[data-ambient="([^"]+)"\]/g,
  effect: /\[data-effect="([^"]+)"\]/g,
  notification_style: /\.ds-notifications(?:--[\w-]+)?\[data-style="([^"]+)"\]/g,
  notification_animation: /\.ds-notifications\[data-animation="([^"]+)"\]/g,
};

interface Held {
  pack: string;
  folder: string;
  type: string;
  look: string;
  render: { kind: string; css?: string[]; file?: string; stage?: boolean };
}

function held(): Held[] {
  const out: Held[] = [];
  for (const pack of readdirSync(PACKS)) {
    const elements = join(PACKS, pack, "elements");
    if (!existsSync(elements)) continue;
    for (const folder of readdirSync(elements)) {
      const element = JSON.parse(readFileSync(join(elements, folder, "element.json"), "utf8"));
      if (element.look && (element.type in HOOKS || element.render?.kind === "glsl"))
        out.push({ pack, folder: join(elements, folder), ...element });
    }
  }
  return out;
}

describe("Portalab's looks in their packs", () => {
  const looks = held();

  it("leaves no look a built-in pack holds in the application's stylesheets (the socle's apart)", () => {
    const moved = new Set(looks.filter((e) => e.pack !== "portalab-socle").map((e) => `${e.type}:${e.look}`));
    const left: string[] = [];
    for (const sheet of SHEETS) {
      const text = readFileSync(join(THEMES, `${sheet}.css`), "utf8");
      for (const [type, hook] of Object.entries(HOOKS))
        for (const match of text.matchAll(hook))
          if (moved.has(`${type}:${match[1]}`)) left.push(`${sheet}.css ${type}:${match[1]}`);
    }
    expect(left).toEqual([]);
  }, 30_000);

  it("draws each moved look by its own stylesheet, every rule of which passes the guard", () => {
    const drawn = looks.filter((e) => e.render.kind === "css");
    expect(drawn.length).toBeGreaterThan(400);
    const cut: string[] = [];
    for (const element of drawn) {
      for (const file of element.render.css ?? []) {
        postcss.parse(readFileSync(join(element.folder, file), "utf8")).walkRules((rule) => {
          if (rule.parent?.type === "atrule" && /keyframes$/i.test((rule.parent as postcss.AtRule).name))
            return;
          for (const selector of splitSelectors(rule.selector))
            if (!lookSelectorOk(selector, element.look))
              cut.push(`${element.type}:${element.look} ${selector}`);
        });
      }
    }
    expect(cut).toEqual([]);
  }, 60_000); // ~500 stylesheets read and parsed

  it("draws each GPU look by its own fragment, none left in the interface's code", () => {
    const drawn = looks.filter((e) => e.render.kind === "glsl");
    expect(drawn.length).toBeGreaterThan(150);
    const wrong: string[] = [];
    for (const element of drawn) {
      const body = readFileSync(join(element.folder, element.render.file ?? "-"), "utf8");
      // an ambience is a whole program after the shared noise; any other look a shape's fragment
      const draws =
        element.type === "ambient"
          ? /void main/.test(body) && /gl_FragColor/.test(body)
          : /\bo\s*=/.test(body);
      if (!draws) wrong.push(`${element.type}:${element.look} draws nothing`);
      if ((element.type === "level_up" || element.type === "effect") && !element.render.stage)
        wrong.push(`${element.type}:${element.look} is not a stage`);
    }
    expect(wrong).toEqual([]);
    const tables = readFileSync(join(THEMES, "premium", "fxLooks.ts"), "utf8");
    expect(tables).not.toMatch(/export const FX_/);
    const ambiences = readFileSync(join(THEMES, "premium", "PremiumAmbient.tsx"), "utf8");
    expect(ambiences).not.toMatch(/const (LAYERS|PREMIUM_FALLBACK)\b/);
  });
});
