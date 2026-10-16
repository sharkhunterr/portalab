import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { act, render, waitFor } from "@testing-library/react";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { AmbientLayer } from "../../src/design-system/themes/AmbientLayer";
import { isPremiumAmbient, premiumFallback } from "../../src/design-system/themes/premium/PremiumAmbient";
import { installElements, uninstallScope } from "../../src/design-system/visuals/registry";

// #68 — premium ambiences drawn on a canvas; when the device cannot (no WebGL, as here), the CSS ambience
// standing for each shows instead — never an empty page. 028: they are their packs' (Portalab's own here,
// read from disk): each element says its layers and its stand-in.

const PACKS = resolve(dirname(fileURLToPath(import.meta.url)), "../../../packs/builtin");
const KINDS = ["inferno", "thunderstorm", "sandstorm", "matrix", "fireworks", "mesh", "orion"];

beforeAll(async () => {
  const elements = readdirSync(PACKS).flatMap((pack) =>
    readdirSync(join(PACKS, pack, "elements")).flatMap((folder) => {
      const element = JSON.parse(readFileSync(join(PACKS, pack, "elements", folder, "element.json"), "utf8"));
      if (element.type !== "ambient" || !KINDS.includes(element.look)) return [];
      const base = `/api/v1/visuals/files/${pack}/0123456789abcdef/${folder}`;
      const render = element.render;
      return [
        {
          pack,
          sha: "0123456789abcdef",
          type: "ambient",
          look: element.look,
          names: {},
          kind: render.kind,
          renderer: render.renderer ?? null,
          params: render.params ?? null,
          file: render.file ? `${base}/${render.file}` : null,
          css: [],
        },
      ];
    }),
  );
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("void main() { gl_FragColor = vec4(0.0); }", { status: 200 })),
  );
  await act(() => installElements(elements as never, "live"));
});

afterAll(() => {
  uninstallScope("live");
  vi.unstubAllGlobals();
});

describe("premium ambiences", () => {
  it("knows which ambiences are drawn on a canvas, each with a CSS stand-in", () => {
    for (const kind of KINDS) {
      expect(isPremiumAmbient(kind), kind).toBe(true);
      expect(premiumFallback(kind), kind).not.toBe("none");
    }
    expect(isPremiumAmbient("snow")).toBe(false);
  });

  it("falls back to the CSS ambience without WebGL", async () => {
    render(<AmbientLayer kind="inferno" />);
    await waitFor(() => expect(document.querySelector('[data-ambient="embers"]')).not.toBeNull());
    expect(document.querySelector('[data-ambient="inferno"]')).toBeNull();
  });
});

describe("live weather ambience", () => {
  it("draws its own sky, the CSS ambience of that weather standing in without WebGL", async () => {
    const { WeatherAmbient } = await import("../../src/design-system/themes/premium/WeatherAmbient");
    render(
      <WeatherAmbient
        contained
        report={{ condition: "snow_showers", intensity: "heavy", phase: "night" }}
        fallback={(kind) => <AmbientLayer kind={kind as "snow"} contained />}
      />,
    );
    await waitFor(() => expect(document.querySelector('[data-ambient="snow"]')).not.toBeNull());
  });
});
