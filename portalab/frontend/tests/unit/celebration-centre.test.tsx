import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// A celebration drawn over the whole screen (GPU or a pack's script) is drawn round the screen's centre: its
// « +40 XP » bubble sits there with it (data-full), not under the header where the CSS ones keep it.

vi.mock("../../src/design-system/visuals/gpu", () => ({
  gpuLook: (_type: string, look: string) => (look === "pluie-or" ? { effect: "x", start: 0 } : undefined),
  useGpuLook: (_type: string, look: string) => (look === "pluie-or" ? { effect: "x", start: 0 } : undefined),
}));
vi.mock("../../src/design-system/components/Fx", () => ({
  FxLayer: ({ className }: { className?: string }) => <canvas className={className} />,
}));

const { CelebrationScene } = await import("../../src/design-system/feedback/Celebration");

describe("a celebration's bubble", () => {
  const event = { kind: "reward", text: "+40 XP" } as const;

  it("sits at the centre of the screen when the GPU draws the celebration over it", () => {
    const { container } = render(<CelebrationScene effect="pluie-or" event={event} />);
    expect(container.querySelector(".ds-celebration")?.getAttribute("data-full")).toBe("true");
    expect(container.querySelector("canvas.celebration-gpu")).not.toBeNull();
  });

  it("stays under the header for a CSS celebration, and when motion is reduced", () => {
    const css = render(<CelebrationScene effect="sparkle" event={event} />);
    expect(css.container.querySelector(".ds-celebration")?.hasAttribute("data-full")).toBe(false);
    const still = render(<CelebrationScene effect="pluie-or" event={event} reduced />);
    expect(still.container.querySelector(".ds-celebration")?.hasAttribute("data-full")).toBe(false);
  });
});
