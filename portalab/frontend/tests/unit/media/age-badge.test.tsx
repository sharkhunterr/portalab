import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AgeBadge, ageTier } from "../../../src/features/media/AgeBadge";

// Issue 434 — a title's age rating as a badge coloured by age, its sources in its tooltip.

describe("the age badge", () => {
  it("bands the ages as the boards draw them", () => {
    expect([0, 3, 7, 10, 12, 15, 16, 17, 18, 21].map(ageTier)).toEqual([
      "all",
      "all",
      "7",
      "7",
      "12",
      "12",
      "16",
      "16",
      "18",
      "18",
    ]);
  });

  it("says the age and its sources; nothing for an unrated title", () => {
    const { container, rerender } = render(<AgeBadge age={16} sources="FR 12 · US R" />);
    const badge = container.querySelector(".age-badge");
    expect(badge?.getAttribute("data-tier")).toBe("16");
    expect(badge?.textContent).toContain("16+");
    expect(badge?.getAttribute("title")).toContain("FR 12 · US R");
    rerender(<AgeBadge age={3} />);
    expect(screen.getByText("All ages")).toBeTruthy();
    rerender(<AgeBadge age={null} />);
    expect(container.querySelector(".age-badge")).toBeNull();
  });
});
