import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { components } from "../../../src/api/generated/schema";
import { RatingsBlock } from "../../../src/features/media/detail/RatingsBlock";

// Issue 478 — a title's classification: its age, the portal's country shown, every other one folded away.

type AgeRating = components["schemas"]["AgeRating"];

const rating = {
  age: 12,
  country: "FR",
  basis: "tv",
  basis_country: null,
  cnc: null,
  warnings: [],
  releases: [
    { country: "US", type: "cinema", certification: "PG-13", note: null, date: null, descriptors: [] },
    { country: "FR", type: "cinema", certification: "U", note: null, date: null, descriptors: [] },
    { country: "FR", type: "tv", certification: "12", note: null, date: null, descriptors: [] },
    { country: "DE", type: "cinema", certification: "12", note: null, date: null, descriptors: [] },
  ],
} as unknown as AgeRating;

describe("the classification block", () => {
  it("shows the age and the portal's country, the other countries folded", () => {
    const { container } = render(<RatingsBlock rating={rating} />);
    expect(container.querySelector(".age-badge")?.textContent).toContain("12+");
    const shown = container.querySelector(".media-ratings > .media-ratings__country");
    expect(shown?.querySelector("h4")?.textContent).toBe("France");
    // its TV rating first, then the cinema's
    expect([...(shown?.querySelectorAll("dt") ?? [])].map((n) => n.textContent)).toEqual(["TV", "Cinema"]);
    const folded = container.querySelector("details.media-ratings__others") as HTMLDetailsElement;
    expect(folded.open).toBe(false);
    expect(screen.getByText("2 other countries")).toBeTruthy();
    expect([...folded.querySelectorAll("h4")].map((n) => n.textContent)).toEqual([
      "Germany",
      "United States",
    ]);
    fireEvent.click(screen.getByText("2 other countries"));
    expect(screen.getByText("PG-13")).toBeTruthy();
  });

  it("folds nothing when only the portal's country rated it", () => {
    const { container } = render(
      <RatingsBlock rating={{ ...rating, releases: rating.releases.filter((r) => r.country === "FR") }} />,
    );
    expect(container.querySelector("details")).toBeNull();
  });
});
