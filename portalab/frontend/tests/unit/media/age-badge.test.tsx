import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AgeBadge, ageTier } from "../../../src/features/media/AgeBadge";
import { Poster } from "../../../src/features/media/MediaGrid";

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

describe("the age badge on thumbnails (issue 434)", () => {
  it("draws « ? » for a title without any rating", () => {
    const { container } = render(<AgeBadge age={-1} compact />);
    const badge = container.querySelector(".age-badge");
    expect(badge?.getAttribute("data-tier")).toBe("unknown");
    expect(badge?.textContent).toContain("?");
    expect(badge?.getAttribute("aria-label") ?? badge?.getAttribute("title")).toContain("Not rated");
  });

  it("asks the ages of a whole shelf in one call", async () => {
    const asked: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        asked.push(url);
        return new Response(JSON.stringify({ ages: { a1: 12, a2: -1 } }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={client}>
        <span className="media-card__frame">
          <Poster src={null} kind="movie" mediaId="a1" />
        </span>
        <span className="media-card__frame">
          <Poster src={null} kind="book" mediaId="a2" />
        </span>
        <span className="media-card__frame">
          <Poster src={null} kind="movie" mediaId="a3" age={16} />
        </span>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(container.querySelectorAll(".age-badge")).toHaveLength(3));
    expect(asked).toEqual(["/api/v1/media/ages?ids=a1,a2"]); // the card that carries its age asks nothing
    expect([...container.querySelectorAll(".age-badge")].map((b) => b.getAttribute("data-tier"))).toEqual([
      "12",
      "unknown",
      "16",
    ]);
    vi.unstubAllGlobals();
  });
});
