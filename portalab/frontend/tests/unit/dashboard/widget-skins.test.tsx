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

  it("counts down to the next event still to come on a flip board, the others listed", () => {
    const items = [
      { title: "Festival under way", route: "/calendar/1", meta: "2020-01-01T20:00:00Z" },
      { title: "Movie night", route: "/calendar/2", meta: "2999-01-01T20:00:00Z" },
    ];
    show("calendar.upcoming", { items }, { style: "flip" });
    expect(document.querySelector(".skin-flip__next")?.textContent).toContain("Movie night");
    expect(screen.getByText("Festival under way")).toBeInTheDocument(); // still in the list
    expect(screen.getByRole("timer").getAttribute("aria-label")).toMatch(/days/);
  });

  it("deals the posters as a deck, the next card on a click", () => {
    show("media.posters", { items: [card(1), card(2), card(3)] }, { style: "deck" });
    expect(document.querySelectorAll(".skin-deck__pile img")).toHaveLength(3);
    expect(screen.getByText("Title 1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next card" }));
    expect(screen.getByText("Title 2")).toBeInTheDocument();
  });

  it("runs the latest news on a ticker, the list kept below; the classic look is the list alone", () => {
    const items = [
      { title: "Server upgraded", route: "/news/1" },
      { title: "Movie night", route: "/news/2" },
    ];
    const classic = show("news.latest", { items });
    expect(document.querySelector(".skin-ticker")).toBeNull();
    expect(screen.getByText("Server upgraded")).toBeInTheDocument();
    classic.unmount();
    show("news.latest", { items }, { style: "ticker" });
    // twice in the lane for the loop, once in the list
    expect(screen.getAllByText("Server upgraded")).toHaveLength(3);
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
