import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import type { AiSource } from "../../../src/features/ai/api";
import { SourceList } from "../../../src/features/ai/sources/SourceList";

// 018 T020 — per-answer sources with text class labels (not color only) and "as of"; caveat note;
// uncited prose labelled as interpretation; only in-portal links are links.

const SOURCES: AiSource[] = [
  {
    n: 1,
    kind: "service",
    ref: "service:s1",
    title: "Media",
    class: "real",
    as_of: "2026-10-01T12:00:00Z",
    url: "/services/s1",
  },
  {
    n: 3,
    kind: "wiki",
    ref: "wiki:7",
    title: "Restart guide",
    class: "knowledge",
    as_of: null,
    url: "https://elsewhere.test/x",
  },
];

function show(props: Parameters<typeof SourceList>[0]) {
  const router = createMemoryRouter([{ path: "/", element: <SourceList {...props} /> }]);
  render(<RouterProvider router={router} />);
}

describe("SourceList", () => {
  it("numbers sources with class labels and dates", () => {
    show({ sources: SOURCES, caveats: [], interpretation: false });
    const items = screen.getAllByRole("listitem");
    expect(items.map((li) => li.getAttribute("value"))).toEqual(["1", "3"]);
    expect(items[0]?.textContent).toContain("Live data");
    expect(items[0]?.textContent).toContain("as of");
    expect(items[1]?.textContent).toContain("Knowledge base");
    expect(screen.getByRole("link", { name: "Media" }).getAttribute("href")).toBe("/services/s1");
    expect(screen.queryByRole("link", { name: "Restart guide" })).toBeNull();
    expect(screen.queryByText(/interpretation/)).toBeNull();
  });

  it("labels interpretation and shows caveats", () => {
    show({
      sources: [],
      caveats: [
        { tool: "wiki.search", state: "unavailable" },
        { tool: "statistics.get", state: "stale" },
      ],
      interpretation: true,
    });
    expect(screen.getByText("Assistant interpretation — not backed by a cited source.")).toBeTruthy();
    const note = screen.getByRole("note");
    expect(note.textContent).toContain("wiki.search was unavailable.");
    expect(note.textContent).toContain("Data from statistics.get may be out of date.");
    expect(screen.queryByRole("list")).toBeNull();
  });
});
