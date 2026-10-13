import { cleanup, render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CountBadge } from "../../src/design-system/components/CountBadge";

// #98 — a small badge and its number where something waits: nothing at zero, « 99+ » past 99, a dot
// where room is short (the number still told to assistive technologies).
describe("CountBadge", () => {
  it("shows nothing at zero and the number otherwise", () => {
    expect(render(<CountBadge count={0} />).container.innerHTML).toBe("");
    cleanup();
    const { getByRole } = render(<CountBadge count={3} label="3 to handle" />);
    expect(getByRole("status").textContent).toBe("3");
    expect(getByRole("status").getAttribute("aria-label")).toBe("3 to handle");
  });

  it("caps the number and draws a dot alone when asked", () => {
    expect(render(<CountBadge count={250} />).getByRole("status").textContent).toBe("99+");
    cleanup();
    const dot = render(<CountBadge count={4} dot label="4 to handle" />).getByRole("status");
    expect(dot.textContent).toBe("");
    expect(dot.getAttribute("data-dot")).toBe("true");
  });
});
