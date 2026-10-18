import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// A celebration drawn by the GPU is drawn round the « +40 XP » bubble: its canvas lives in the bubble's own box
// (under the header, where the bubble stays) and is centred on it by its stylesheet — the bubble never moves.

vi.mock("../../src/design-system/visuals/gpu", () => ({
  gpuLook: (_type: string, look: string) => (look === "pluie-or" ? { effect: "x", start: 0 } : undefined),
  useGpuLook: (_type: string, look: string) => (look === "pluie-or" ? { effect: "x", start: 0 } : undefined),
}));
vi.mock("../../src/design-system/components/Fx", () => ({
  FxLayer: ({ className }: { className?: string }) => <canvas className={className} />,
}));

const { CelebrationScene } = await import("../../src/design-system/feedback/Celebration");

describe("an HD celebration", () => {
  const event = { kind: "reward", text: "+40 XP" } as const;

  it("draws its scene in the bubble's box, the bubble staying in its place", () => {
    const { container } = render(<CelebrationScene effect="pluie-or" event={event} />);
    const box = container.querySelector(".ds-celebration");
    expect(box?.querySelector(":scope > canvas.celebration-gpu")).not.toBeNull();
    expect(box?.querySelector(":scope > .ds-celebration__badge")?.textContent).toBe("+40 XP");
    expect(box?.hasAttribute("data-full")).toBe(false);
  });

  it("draws no scene when motion is reduced", () => {
    const { container } = render(<CelebrationScene effect="pluie-or" event={event} reduced />);
    expect(container.querySelector("canvas.celebration-gpu")).toBeNull();
  });
});
