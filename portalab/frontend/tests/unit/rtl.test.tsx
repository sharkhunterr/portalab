import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  DirectionProvider,
  directionOf,
  mirrorStyle,
  useDirection,
} from "../../src/design-system/rtl/DirectionProvider";

// 022 T022 — dir/lang from the locale; logical properties (no left/right in DS CSS); directional icons mirror.

function Probe() {
  const { direction } = useDirection();
  return <span data-testid="dir">{direction}</span>;
}

describe("direction", () => {
  it("sets dir and lang from the locale", () => {
    const { getByTestId, rerender } = render(
      <DirectionProvider language="ar-EG">
        <Probe />
      </DirectionProvider>,
    );
    expect(getByTestId("dir")).toHaveTextContent("rtl");
    expect(document.documentElement.dir).toBe("rtl");
    expect(document.documentElement.lang).toBe("ar-EG");
    rerender(
      <DirectionProvider language="fr">
        <Probe />
      </DirectionProvider>,
    );
    expect(document.documentElement.dir).toBe("ltr");
    expect(directionOf("he")).toBe("rtl");
  });

  it("mirrors directional icons only", () => {
    expect(mirrorStyle("chevron-right", "rtl")).toEqual({ transform: "scaleX(-1)" });
    expect(mirrorStyle("check", "rtl")).toEqual({});
    expect(mirrorStyle("chevron-right", "ltr")).toEqual({});
  });

  it("design-system CSS uses logical properties", async () => {
    const { readFileSync } = await import("node:fs");
    const { join } = await import("node:path");
    const css = readFileSync(join(process.cwd(), "src/design-system/components/components.css"), "utf8");
    expect(css).not.toMatch(/(?:margin|padding)-(?:left|right)|(?<![-\w])(?:left|right):/);
  });
});
