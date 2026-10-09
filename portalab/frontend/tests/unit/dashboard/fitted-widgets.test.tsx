import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// 027 (#12) — « shuffle »: one title drawn from the batch with its year, kind, genres and overview, its
// posters looping behind as a frieze, « another one » never draws the same twice in a row; « my
// progression »: the level as a ring filled up to the next one and the three values as chips.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import "../../../src/features/dashboard/widgets/media";
import "../../../src/features/gamification/widget";
import { widgetComponent } from "../../../src/features/dashboard/widgets/registry";
import { json } from "../../support/fake-api";

function show(key: string, data: unknown) {
  const Widget = widgetComponent(key);
  expect(Widget).toBeDefined();
  const Component = Widget as NonNullable<typeof Widget>;
  const element: ReactElement = <Component payload={{ state: "available", data } as never} config={{}} />;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter([{ path: "/", element }])} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

const card = (n: number) => ({
  id: `id${n}`,
  title: `Title ${n}`,
  kind: "movie",
  year: 2000 + n,
  genres: ["Sci-Fi"],
  overview: `Overview ${n}`,
  image_id: `img${n}`,
  route: `/media/id${n}`,
});

describe("shuffle", () => {
  it("shows one title of the batch, its posters looping behind, and draws another one", () => {
    const random = vi.spyOn(Math, "random").mockReturnValue(0); // the first card first
    show("media.shuffle", { items: [card(1), card(2), card(3)] });
    expect(screen.getByText("Title 1")).toBeTruthy();
    expect(screen.getByText(/2001 · Movie · Sci-Fi/)).toBeTruthy();
    expect(screen.getByText("Overview 1")).toBeTruthy();
    expect(screen.getByRole("link", { name: /See the title/ }).getAttribute("href")).toBe("/media/id1");
    expect(document.querySelectorAll(".widget-shuffle__track img")).toHaveLength(6); // twice, for the loop
    random.mockReturnValueOnce(0).mockReturnValueOnce(0.5); // the same one first: drawn again
    fireEvent.click(screen.getByRole("button", { name: /Another one/ }));
    expect(screen.getByText("Title 2")).toBeTruthy();
  });

  it("says so when there is nothing to draw", () => {
    show("media.shuffle", { items: [] });
    expect(screen.getByText("Nothing to draw yet.")).toBeTruthy();
  });
});

describe("my progression", () => {
  it("shows the level as a ring filled up to the next one, and the values as chips", async () => {
    fake.handler = () => json(200, { level: 12, xp: 1500, level_floor: 1000, next_level_at: 2000 });
    show("gamification.progress", { level: 12, xp: 1500, coins: 956535, contribution: 32 });
    const ring = await screen.findByRole("progressbar", { name: "Level 12" });
    expect(await screen.findByText("500 / 1,000 XP")).toBeTruthy();
    expect(ring.getAttribute("aria-valuenow")).toBe("50");
    expect(screen.getByText("956.5K")).toBeTruthy(); // a large figure in a small place
  });
});
