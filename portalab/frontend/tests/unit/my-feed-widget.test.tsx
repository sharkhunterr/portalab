import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import "../../src/features/news/MyFeedWidget";
import { widgetComponent } from "../../src/features/dashboard/widgets/registry";
import { embeddable, youtubeId } from "../../src/features/news/YouTube";

// issue 315 — « Mon fil » on the dashboard: the latest news with their source, the latest only on one row;
// a YouTube video plays in place, only once asked for, from YouTube's privacy-enhanced player.

const now = new Date().toISOString();
const ITEMS = [
  {
    id: "1",
    title: "The trailer is out",
    summary: "Two minutes of it.",
    link: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    source: "Trailers",
    source_kind: "youtube",
    source_index: 0,
    picture: "/api/v1/news/sources/items/1/picture",
    published_at: now,
  },
  {
    id: "2",
    title: "A festival opens",
    summary: "",
    link: "https://news.example.org/festival",
    source: "Écrans",
    source_kind: "rss",
    source_index: 1,
    picture: null,
    published_at: now,
  },
];

const show = (compact = false) => {
  const Widget = widgetComponent("news.my_feed");
  if (!Widget) throw new Error("no news.my_feed");
  return render(
    <MemoryRouter>
      <Widget
        payload={{ state: "available", data: { items: ITEMS } } as never}
        config={{}}
        compact={compact}
      />
    </MemoryRouter>,
  );
};

describe("issue 315 — my feed's widget", () => {
  it("lists the news with their source and plays a YouTube video in place on demand", () => {
    const { container } = show();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("Écrans")).toBeInTheDocument();
    expect(container.querySelector("iframe")).toBeNull(); // nothing from YouTube before a click
    expect(screen.getAllByRole("button", { name: /Play/ })).toHaveLength(1); // the article is no video
    fireEvent.click(screen.getByRole("button", { name: /Play/ }));
    const frame = container.querySelector("iframe");
    expect(frame?.getAttribute("src")).toMatch(/^https:\/\/www\.youtube-nocookie\.com\/embed\/dQw4w9WgXcQ\?/);
    expect(frame?.getAttribute("sandbox")).not.toContain("allow-top-navigation");
    fireEvent.click(screen.getByRole("button", { name: /Close the video/ }));
    expect(container.querySelector("iframe")).toBeNull();
  });

  it("shows the latest only on a single row, leading to my feed", () => {
    show(true);
    expect(screen.getByText("The trailer is out").closest("a")?.getAttribute("href")).toBe("/feed");
    expect(screen.queryByText("A festival opens")).toBeNull();
  });

  it("tells a YouTube video by its address, however it is written", () => {
    expect(youtubeId("https://youtu.be/dQw4w9WgXcQ?t=3")).toBe("dQw4w9WgXcQ");
    expect(youtubeId("https://m.youtube.com/shorts/dQw4w9WgXcQ")).toBe("dQw4w9WgXcQ");
    expect(youtubeId("https://www.youtube.com/channel/UC123")).toBeNull();
    expect(youtubeId("https://evil.example/watch?v=dQw4w9WgXcQ")).toBeNull();
  });

  it("plays in place under a host name only — YouTube refuses a page reached by its IP address", () => {
    expect(embeddable("portalab.lan")).toBe(true);
    expect(embeddable("localhost")).toBe(true);
    expect(embeddable("192.168.1.40")).toBe(false);
    expect(embeddable("[::1]")).toBe(false);
  });
});
