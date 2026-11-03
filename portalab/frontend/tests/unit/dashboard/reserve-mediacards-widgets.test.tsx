import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import "../../../src/features/marketplace/reserve/ReserveWidget";
import "../../../src/features/cards/CollectionWidget";
import { widgetComponent } from "../../../src/features/dashboard/widgets/registry";

// issue 347 — « My reserve » counts what waits in the reserve by its page's sections (my card boosters among
// those to open, unless I play without the cards), its first things as tiles, stacked; « My Mediacards »
// tells where my collection stands and stacks my sealed packs, leading to the « To open » view. On a single
// row, both show their figures only.

const pack = (id: string) => ({
  id,
  source: "content",
  set: "s1",
  set_name: "Dune",
  look: null,
  given_at: "2026-11-01T10:00:00Z",
  opened_at: null,
  cards: [],
  count: 3,
});

function show(key: string, data: unknown, { compact = false, play = null as string | null } = {}) {
  const Widget = widgetComponent(key);
  if (!Widget) throw new Error(`no ${key}`);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: false, staleTime: Number.POSITIVE_INFINITY } },
  });
  client.setQueryData(["me", "preferences", "shell"], play ? { "shell.onboarding.play": play } : {});
  client.setQueryData(["cards", "packs"], [pack("p1")]);
  const element = <Widget payload={{ state: "available", data } as never} config={{}} compact={compact} />;
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter([{ path: "/", element }])} />
    </QueryClientProvider>,
  );
}

const RESERVE = {
  counts: { todo: 1, open: 2, use: 3, waiting: 0 },
  new: 2,
  items: [
    { key: "film", name: "A film in 4K", type: "media_request", quantity: 1, section: "todo" },
    { key: "booster_looks", name: "Looks booster", type: "booster", quantity: 2, section: "open", new: true },
    { key: "plus_3", name: "+3 requests", type: "quota", rarity: "rare", quantity: 3, section: "use" },
  ],
};

describe("issue 347 — my reserve's widget", () => {
  it("counts each section, my card boosters among those to open, and stacks identical things", () => {
    show("marketplace.reserve", RESERVE);
    const counts = screen.getByRole("list", { name: "What waits in my reserve" });
    expect(counts.textContent).toContain("1To complete");
    expect(counts.textContent).toContain("3To open"); // 2 sealed boosters and a pack of cards
    expect(counts.textContent).toContain("3To use");
    expect(counts.textContent).not.toContain("Waiting");
    const tile = screen.getByText("+3 requests").closest("a");
    expect(tile?.getAttribute("href")).toBe("/marketplace/reserve");
    expect(tile?.textContent).toContain("×3");
    expect(screen.getByText("Looks booster").closest("li")?.textContent).toContain("new");
  });

  it("leaves my card boosters out when I play without the cards", () => {
    show("marketplace.reserve", RESERVE, { play: "progression" });
    expect(screen.getByRole("list", { name: "What waits in my reserve" }).textContent).toContain("2To open");
  });

  it("shows the counts only on a single row", () => {
    show("marketplace.reserve", RESERVE, { compact: true });
    expect(screen.getByText("1 to complete · 3 to open · 3 to use")).toBeInTheDocument();
    expect(screen.queryByText("+3 requests")).toBeNull();
  });
});

const MINE = {
  unique: 142,
  cards: 1280,
  sets_started: 18,
  sets: 96,
  copies: 231,
  unopened: 2,
  packs: [pack("p1"), pack("p2")],
};

describe("issue 347 — my Mediacards' widget", () => {
  it("tells where my collection stands and stacks my identical packs, leading to those to open", () => {
    show("cards.collection", MINE);
    expect(screen.getByRole("region", { name: "My collection" }).textContent).toContain("142 / 1,280 cards");
    expect(screen.getByText("231")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "2 packs to open" }).getAttribute("href")).toBe(
      "/cards?vue=boosters",
    );
    const piles = document.querySelectorAll(".mediacards-widget__pack");
    expect(piles).toHaveLength(1); // the same booster twice: one pile
    expect(piles[0]?.getAttribute("data-pile")).toBe("true");
  });

  it("shows the figures only on a single row", () => {
    show("cards.collection", MINE, { compact: true });
    expect(screen.getByText("142 / 1,280 cards")).toBeInTheDocument();
    expect(screen.getByText("2 packs to open").closest("a")?.getAttribute("href")).toBe(
      "/cards?vue=boosters",
    );
    expect(document.querySelector(".mediacards-widget__pack")).toBeNull();
  });
});
