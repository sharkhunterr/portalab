import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// Issue 465 — a title's videos and pictures on its page: trailers first, by kind when there are several; a
// YouTube video played in place by YouTube's privacy-enhanced player, a media server's extra in the portal's
// player; the pictures opening a viewer that turns them with buttons, the arrow keys or a swipe.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { clock, Extras } from "../../../src/features/media/detail/Extras";
import { json } from "../../support/fake-api";

const ID = "0190f0a0-0000-7000-8000-0000000000b2";
const BASE = `/api/v1/media/${ID}/extras`;
const EXTRAS = {
  videos: [
    {
      index: 0,
      site: "youtube",
      youtube: "abcdefghijk",
      play: null,
      name: "Official trailer",
      kind: "trailer",
      language: "en",
      duration_s: 125,
      picture: `${BASE}/videos/0/picture`,
    },
    {
      index: 1,
      site: "service",
      youtube: null,
      play: `/media/${ID}/watch?item=51`,
      name: "Making of",
      kind: "behind_the_scenes",
      language: null,
      duration_s: null,
      picture: null,
    },
  ],
  images: [0, 1, 2].map((index) => ({
    index,
    kind: "backdrop",
    preview: `${BASE}/images/${index}?preview=true`,
    full: `${BASE}/images/${index}`,
  })),
};

function renderExtras(extras: unknown) {
  fake.handler = (request) => (new URL(request.url).pathname === BASE ? json(200, extras) : json(404, {}));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider
        router={createMemoryRouter(
          [
            { path: "/media/:id", element: <Extras objectId={ID} title="Film" /> },
            { path: "/media/:id/watch", element: <p>The player</p> },
          ],
          { initialEntries: [`/media/${ID}`] },
        )}
      />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("a title's extras", () => {
  it("shows nothing when no service knows any", async () => {
    const { container } = renderExtras({ videos: [], images: [] });
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(container.textContent).toBe("");
  });

  it("lists the videos by kind and plays a YouTube one in place", async () => {
    renderExtras(EXTRAS);
    const list = await screen.findByRole("list", { name: "Videos" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
    expect(within(list).getByText("Trailer · EN · 2:05")).toBeTruthy();
    // by kind: « Behind the scenes » alone
    fireEvent.click(screen.getByRole("button", { name: "Behind the scenes" }));
    expect(within(list).getAllByRole("listitem")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "All" }));
    // YouTube's privacy-enhanced player, only once asked
    expect(document.querySelector("iframe")).toBeNull();
    fireEvent.click(within(list).getByRole("button", { name: "Play “Official trailer”" }));
    const dialog = await screen.findByRole("dialog", { name: "Official trailer" });
    const frame = within(dialog).getByTitle("Official trailer");
    expect(frame.getAttribute("src")).toContain("https://www.youtube-nocookie.com/embed/abcdefghijk");
  });

  it("plays a media server's extra in the portal's player", async () => {
    renderExtras(EXTRAS);
    fireEvent.click(await screen.findByRole("link", { name: "Play “Making of”" }));
    expect(await screen.findByText("The player")).toBeTruthy();
  });

  it("turns the pictures in the viewer", async () => {
    renderExtras(EXTRAS);
    const pictures = await screen.findByRole("list", { name: "Pictures" });
    fireEvent.click(within(pictures).getByRole("button", { name: "Open picture 2 of 3" }));
    const viewer = await screen.findByRole("dialog", { name: "Pictures of Film" });
    const shown = () => viewer.querySelector("figure img")?.getAttribute("src");
    expect(shown()).toBe(`${BASE}/images/1`);
    fireEvent.click(within(viewer).getByRole("button", { name: "Next picture" }));
    expect(shown()).toBe(`${BASE}/images/2`);
    fireEvent.keyDown(viewer, { key: "ArrowRight" }); // past the last: the first
    expect(shown()).toBe(`${BASE}/images/0`);
    fireEvent.keyDown(viewer, { key: "ArrowLeft" });
    expect(shown()).toBe(`${BASE}/images/2`);
    expect(within(viewer).getByText("3 / 3")).toBeTruthy();
    // a swipe to the left: the next one
    const stage = viewer.querySelector("figure") as HTMLElement;
    fireEvent.pointerDown(stage, { clientX: 300 });
    fireEvent.pointerUp(stage, { clientX: 200 });
    expect(shown()).toBe(`${BASE}/images/0`);
    fireEvent.click(within(viewer).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("clock", () => {
  it("tells a video's length", () => {
    expect(clock(65)).toBe("1:05");
    expect(clock(3725)).toBe("1:02:05");
  });
});
