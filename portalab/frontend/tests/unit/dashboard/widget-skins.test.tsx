import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import "../../../src/features/dashboard/widgets/builtin";
import "../../../src/features/dashboard/widgets/layout";
import "../../../src/features/dashboard/widgets/media";
import "../../../src/features/dashboard/widgets/discover";
import { widgetComponent } from "../../../src/features/dashboard/widgets/registry";
import { partOf } from "../../../src/features/dashboard/widgets/skins";
import { cumulate } from "../../../src/features/gamification/ProgressCurves";

// 027 (#31) — the widgets' other looks: the classic look stays the default (and what a member who did not
// buy another one sees), a look is picked with ``style``; and the three media widgets « living wall »,
// « playing on the server » and « a year ago ».

function show(key: string, data: unknown, config: Record<string, unknown> = {}) {
  const Widget = widgetComponent(key);
  expect(Widget, key).toBeDefined();
  const Component = Widget as NonNullable<typeof Widget>;
  const element: ReactElement = <Component payload={{ state: "available", data } as never} config={config} />;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, enabled: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter([{ path: "/", element }])} />
    </QueryClientProvider>,
  );
}

const card = (n: number) => ({
  id: `id${n}`,
  title: `Title ${n}`,
  kind: "movie",
  image_id: `img${n}`,
  route: `/media/id${n}`,
});

describe("widget looks", () => {
  it("keeps the classic look by default and draws the analog clock when picked", () => {
    const classic = show("dashboard.clock", { seconds: true, date: true });
    expect(document.querySelector(".widget-clock__time")).not.toBeNull();
    classic.unmount();
    show("dashboard.clock", { seconds: true, date: true }, { style: "analog" });
    expect(document.querySelector(".widget-clock")).toBeNull();
    expect(document.querySelectorAll(".skin-analog__tick")).toHaveLength(12);
    expect(document.querySelector(".skin-analog__second")).not.toBeNull();
  });

  it("lights each poster of « continue » with its own colours, never the whole block", () => {
    const classic = show("media.continue", { items: [card(1), card(2)] });
    expect(document.querySelector(".widget-continue__glow")).toBeNull();
    classic.unmount();
    show("media.continue", { items: [card(1), card(2)] }, { style: "ambient" });
    const glows = document.querySelectorAll<HTMLElement>(".widget-continue__glow");
    expect(glows).toHaveLength(2);
    expect(glows[0]?.style.backgroundImage).toContain("/api/v1/media/images/img1");
  });

  it("draws a heartbeat under the services, in the tone of their health", () => {
    show(
      "health.services_summary",
      {
        items: [{ id: "s1", name: "Plex", state: "degraded", route: "/services/s1" }],
        counts: { degraded: 1 },
      },
      { style: "pulse" },
    );
    expect(document.querySelector('.skin-pulse[data-tone="warn"] .skin-pulse__beam')).not.toBeNull();
    expect(screen.getByText("Plex")).toBeInTheDocument();
  });

  it("shows a countdown on a flip board", () => {
    show("dashboard.countdown", { label: "Holidays", date: "2999-01-01" }, { style: "flip" });
    expect(document.querySelectorAll(".skin-flip__digit").length).toBeGreaterThan(2);
    expect(screen.getByText("Holidays")).toBeInTheDocument();
  });

  it("tells about the card on top of the deck: kind, year, genres, rating and overview", () => {
    const shown = { ...card(1), year: 2024, genres: ["Sci-Fi", "Drama"], rating: 7.8, overview: "Far away." };
    show("media.posters", { items: [shown, card(2)] }, { style: "deck" });
    expect(screen.getByText("Movie · 2024 · Sci-Fi · Drama")).toBeInTheDocument();
    expect(screen.getByText("7.8")).toBeInTheDocument();
    expect(screen.getByText("Far away.")).toBeInTheDocument();
  });

  it("deals the posters as a deck, the next card on a click", () => {
    show("media.posters", { items: [card(1), card(2), card(3)] }, { style: "deck" });
    expect(document.querySelectorAll(".skin-deck__pile img")).toHaveLength(3);
    expect(screen.getByText("Title 1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next card" }));
    expect(screen.getByText("Title 2")).toBeInTheDocument();
  });

  it("shows the latest news one at a time, then the next; the classic look is the list", () => {
    const items = [
      { title: "Server upgraded", route: "/news/1", meta: "2026-10-04", summary: "More room.", cover: "c1" },
      { title: "Movie night", route: "/news/2", meta: "2026-10-02", summary: "Friday.", cover: "c2" },
    ];
    const classic = show("news.latest", { items });
    expect(document.querySelector(".skin-carousel")).toBeNull();
    expect(screen.getByText("Movie night")).toBeInTheDocument();
    classic.unmount();
    show("news.latest", { items }, { style: "carousel" });
    expect(screen.getByText("Server upgraded")).toBeInTheDocument();
    expect(screen.getByText("More room.")).toBeInTheDocument();
    expect(screen.queryByText("Movie night")).toBeNull(); // one at a time
    expect(document.querySelectorAll(".skin-carousel__bars > span")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Next article" }));
    expect(screen.getByText("Movie night")).toBeInTheDocument();
    expect(screen.queryByText("Server upgraded")).toBeNull();
  });

  it("counts a figure up with its separators in place", () => {
    expect(partOf("1,234", 1)).toBe("1,234");
    expect(partOf("1,234", 0.5)).toBe("617");
    expect(partOf("12.5", 0.5)).toBe("6.3");
    expect(partOf("42", 0)).toBe("0");
  });
});

describe("living wall", () => {
  it("fills the wall with posters, keeping some aside to turn in", () => {
    show("media.living_wall", { items: Array.from({ length: 30 }, (_, i) => card(i)) });
    expect(document.querySelectorAll(".widget-living-wall > li")).toHaveLength(24);
    show("media.living_wall", { items: [card(1), card(2), card(3)] });
    expect(document.querySelectorAll(".widget-living-wall > li")).toHaveLength(24 + 2);
  });
});

describe("playing on the server", () => {
  it("lists what plays now, with its progress and the viewer's own marked", () => {
    show("media.server_playing", {
      count: 2,
      items: [
        { ...card(1), state: "playing", progress: 0.5, mine: true },
        { ...card(2), title: "Arcane", subtitle: "Episode 3", state: "paused", progress: 0.1, mine: false },
      ],
    });
    expect(screen.getByText("2 streams")).toBeInTheDocument();
    expect(screen.getByText("You")).toBeInTheDocument();
    expect(screen.getByText("Paused")).toBeInTheDocument();
    expect(screen.getByText("Episode 3")).toBeInTheDocument();
    expect(screen.getAllByRole("progressbar")[0]?.getAttribute("aria-valuenow")).toBe("50");
  });

  it("says when nothing plays", () => {
    show("media.server_playing", { count: 0, items: [] });
    expect(screen.getByText("Nothing is playing right now.")).toBeInTheDocument();
  });
});

describe("next releases", () => {
  it("counts down to the soonest, says why it is there, and brings another forward", () => {
    const at = (days: number) => new Date(Date.now() + days * 86_400_000 + 3_600_000).toISOString();
    show("media.next_releases", {
      items: [
        {
          ...card(1),
          title: "Severance",
          kind: "episode",
          season: 2,
          episode: 5,
          type: "air",
          at: at(3),
          reason: "watching",
          overview: "A dark office.",
        },
        { ...card(2), title: "Dune: Part Three", type: "cinema", at: at(20), reason: "requested" },
      ],
    });
    expect(document.querySelector(".widget-next__title")?.textContent).toBe("Severance");
    expect(screen.getByText("A dark office.")).toBeInTheDocument(); // what it is, where the countdown was
    expect(screen.getByText("You follow it")).toBeInTheDocument();
    expect(screen.getByText(/S02E05/)).toBeInTheDocument();
    const units = document.querySelectorAll(".widget-next__unit strong");
    expect(units).toHaveLength(4);
    expect(units[0]?.textContent).toBe("03");
    fireEvent.click(screen.getByRole("button", { name: /Dune: Part Three/ }));
    expect(document.querySelector(".widget-next__title")?.textContent).toBe("Dune: Part Three");
    expect(screen.getByText("You asked for it")).toBeInTheDocument();
  });

  it("says when nothing followed comes out soon", () => {
    show("media.next_releases", { items: [] });
    expect(screen.getByText("Nothing you follow comes out in the next two months.")).toBeInTheDocument();
  });
});

describe("a year ago", () => {
  it("shows what I watched and what came in, around this date back then", () => {
    show("media.on_this_day", {
      years: 1,
      date: "2025-10-09",
      watched: [card(1)],
      added: [card(2), card(3)],
    });
    expect(screen.getByText(/A year ago ·/)).toBeInTheDocument();
    expect(screen.getByText("You watched")).toBeInTheDocument();
    expect(screen.getByText("New in the library")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Title 1/ }).getAttribute("href")).toBe("/media/id1");
  });

  it("says when past years have nothing", () => {
    show("media.on_this_day", { years: null, watched: [], added: [] });
    expect(screen.getByText("Nothing around this date in past years yet.")).toBeInTheDocument();
  });
});

describe("my progression as curves", () => {
  it("sums the gains of each day of the period into a rising curve", () => {
    const today = new Date("2026-10-09T12:00:00Z");
    const points = cumulate(
      [
        { day: "2026-10-07", amounts: { media: 30, quests: 20 } },
        { day: "2026-10-09", amounts: { media: 10 } },
      ],
      today,
      4,
    );
    expect(points).toEqual([
      { day: "2026-10-06", total: 0 },
      { day: "2026-10-07", total: 50 },
      { day: "2026-10-08", total: 50 },
      { day: "2026-10-09", total: 60 },
    ]);
  });
});
