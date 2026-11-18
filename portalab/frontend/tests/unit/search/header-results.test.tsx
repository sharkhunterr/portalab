import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Issue 502: the header's search shows each type's titles (three), how many match in all and « See all »;
// the calendar's coming episodes never hide their series, tell their kind and their day, show its poster,
// and fold the other dates of the same series into the first.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { json } from "../../support/fake-api";
import { renderShell, VIEW } from "../shell/harness";

const SERIES = "/media/s1";
const episode = (n: number, when: string) => ({
  kind: "calendar",
  id: `media_release:episode:Harry Potter S01E0${n}:${when}`,
  title: `Harry Potter S01E0${n}`,
  url_ref: SERIES,
  facets: {
    source: "media_release",
    status: "scheduled",
    when,
    category: "series",
    image: "/api/v1/media/images/i1",
  },
  group: "search.kind.calendar",
});
const film = (n: number) => ({
  kind: "media",
  id: `m${n}`,
  title: `Harry Potter ${n}`,
  url_ref: `/media/m${n}`,
  facets: { type: "movie", status: "available", of: "8" },
  group: "search.kind.media",
});

describe("the header's results", () => {
  it("lists each type's titles with their total, and the calendar's dates beside their series", async () => {
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/search/suggest")
        return json(200, {
          items: [
            episode(1, "2026-12-25"),
            episode(2, "2027-01-03"),
            episode(3, "2027-01-10"),
            film(1),
            film(2),
            film(3),
            {
              kind: "media",
              id: "s1",
              title: "Harry Potter (2026)",
              url_ref: SERIES,
              facets: { type: "series", status: "requested", of: "1" },
              group: "search.kind.media",
            },
          ],
        });
      if (path === "/api/v1/palette/resolve")
        return json(200, { destinations: [], actions: [], object: null });
      return json(200, VIEW);
    };
    renderShell({ slots: { ai: { available: false, open: vi.fn() } } });
    await screen.findByRole("link", { name: "Services" });
    const input = screen.getAllByRole("combobox", { name: "Search" })[0] as HTMLInputElement;
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "harry potter" } });
    const list = await screen.findByRole("listbox");
    const texts = () =>
      within(list)
        .queryAllByRole("option")
        .map((o) => o.textContent ?? "");
    await waitFor(() => expect(texts().some((t) => t.includes("Harry Potter 3"))).toBe(true));
    // the series stays, although its coming episodes open its page too
    expect(texts().some((t) => t.includes("Harry Potter (2026)"))).toBe(true);
    // one calendar line for the series' dates: its kind, its state in words, its day and the others folded
    const options = within(list).getAllByRole("option");
    const dated = options.filter((o) => o.textContent?.includes("S01E0"));
    expect(dated).toHaveLength(1);
    const line = dated[0] as HTMLElement;
    expect(line.textContent).toContain("Series");
    expect(line.textContent).toContain("Upcoming");
    expect(line.textContent).toContain("2 more dates");
    expect(line.textContent).toContain("2026");
    expect(line.querySelector("img")?.getAttribute("src")).toBe("/api/v1/media/images/i1");
    // the films: three shown of eight — the heading's count opens all eight (no extra line)
    expect(options.some((o) => o.textContent?.includes("See all"))).toBe(false);
    const all = list.querySelector<HTMLButtonElement>(".header-search__count[data-more]");
    expect(all?.textContent).toBe("8");
    expect(all?.title).toBe("See all 8 films");
    fireEvent.click(all as HTMLButtonElement);
    expect(input.value).toBe("");
  });

  it("asks again when a source did not answer in time, rather than keep « nothing »", async () => {
    let asked = 0;
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/search/suggest") {
        asked += 1;
        return asked === 1
          ? json(200, { items: [], partial: true })
          : json(200, { items: [film(1)], partial: false });
      }
      if (path === "/api/v1/palette/resolve")
        return json(200, { destinations: [], actions: [], object: null });
      return json(200, VIEW);
    };
    renderShell({ slots: { ai: { available: false, open: vi.fn() } } });
    await screen.findByRole("link", { name: "Services" });
    const input = screen.getAllByRole("combobox", { name: "Search" })[0] as HTMLInputElement;
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "harry" } });
    const list = await screen.findByRole("listbox");
    await waitFor(
      () =>
        expect(
          within(list)
            .queryAllByRole("option")
            .some((o) => o.textContent?.includes("Harry Potter 1")),
        ).toBe(true),
      { timeout: 4000 },
    );
    expect(asked).toBe(2);
  });
});
