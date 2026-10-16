import { afterEach, describe, expect, it, vi } from "vitest";
import { gpuLook } from "../../../src/design-system/visuals/gpu";
import { externalFx, installElements, uninstallScope } from "../../../src/design-system/visuals/registry";

// 028 (B2): a GPU look is found in its pack — Portalab's own included — with how it is drawn; a badge's and a
// title's styles are one vocabulary; a look of CSS only is no GPU look.

const element = (type: string, look: string, render: Record<string, unknown>) => ({
  pack: "portalab-base",
  sha: "0123456789abcdef",
  type,
  look,
  names: {},
  css: [],
  ...render,
});

afterEach(() => {
  uninstallScope("live");
  vi.unstubAllGlobals();
});

describe("GPU looks from their packs", () => {
  it("resolves the effect, its shape, radius, timeline and cycle", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("  o = over(o, vec3(1.0), 1.0);\\n", { status: 200 })),
    );
    await installElements(
      [
        element("avatar_frame", "chronogate", {
          kind: "glsl",
          file: "/api/v1/visuals/files/portalab-base/0123456789abcdef/frame/chrono.glsl",
          shape: 5,
          cycle: true,
        }),
        element("effect", "nova", {
          kind: "glsl",
          file: "/api/v1/visuals/files/portalab-base/0123456789abcdef/nova/supernova.glsl",
          stage: true,
          start: 0.3,
        }),
        element("badge", "blaze", {
          kind: "glsl",
          file: "/api/v1/visuals/files/portalab-base/0123456789abcdef/badge/blaze.glsl",
          radius: "50%",
        }),
        element("profile_banner", "aurora", { kind: "css" }),
      ] as never,
      "live",
    );
    const frame = gpuLook("avatar_frame", "chronogate");
    expect(frame).toMatchObject({ shape: 5, cycle: true, stage: false, start: 0 });
    expect(externalFx(frame?.effect ?? "")?.body).toContain("o = over");
    expect(gpuLook("effect", "nova")).toMatchObject({ stage: true, start: 0.3 });
    expect(gpuLook("title", "blaze")).toMatchObject({ radius: "50%" }); // a title wears a badge's style
    expect(gpuLook("profile_banner", "aurora")).toBeUndefined();
    expect(gpuLook("avatar_frame", "unknown")).toBeUndefined();
  });
});
