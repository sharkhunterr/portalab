import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 027 T095 — news as a magazine (featured hero, category chips, cards that are one link each) and my
// tickets with translated state badges and an in-progress / done filter; axe clean.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));

vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { NewsPage } from "../../src/features/news/NewsPage";
import { MyTickets } from "../../src/features/support/tickets/MyTickets";
import { json } from "../support/fake-api";

function withClient(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <main>{children}</main>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const card = (id: string, title: string, category_id: string | null = null) => ({
  id,
  slug: id,
  title,
  summary: `${title} summary`,
  status: "published",
  category_id,
  published_at: "2026-10-04T08:00:00Z",
});

async function expectAccessible(container: HTMLElement) {
  const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  expect(results.violations.map((violation) => violation.id)).toEqual([]);
}

describe("content pages", () => {
  it("news shows the featured hero, filters by category and links each card", async () => {
    const asked: string[] = [];
    fake.handler = (request) => {
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/news/featured") return json(200, [card("hello", "Hello world", "c1")]);
      if (url.pathname === "/api/v1/news/categories")
        return json(200, [{ id: "c1", key: "events", name: "Events", enabled: true, position: 0 }]);
      asked.push(url.searchParams.get("category") ?? "");
      return json(200, {
        items: [card("hello", "Hello world", "c1"), card("other", "Other news")],
        next_cursor: null,
      });
    };
    const { container } = render(withClient(<NewsPage />));
    const featured = await screen.findByRole("region", { name: "Featured" });
    expect(within(featured).getByText("Featured")).toBeInTheDocument();
    expect(within(featured).getByRole("link", { name: "Hello world" })).toHaveAttribute(
      "href",
      "/news/hello",
    );
    const latest = await screen.findByRole("list", { name: "Latest news" });
    expect(within(latest).getAllByRole("link")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Events" }));
    await vi.waitFor(() => expect(asked).toContain("events"));
    await expectAccessible(container);
  });

  it("my tickets translate states and filter what is still in progress", async () => {
    fake.handler = () =>
      json(200, [
        {
          id: "t1",
          reference: "T-1",
          title: "Cannot play",
          state: "waiting_user",
          priority: "high",
          updated_at: "2026-10-04T08:00:00Z",
        },
        {
          id: "t2",
          reference: "T-2",
          title: "Old one",
          state: "resolved",
          priority: "normal",
          updated_at: "2026-10-01T08:00:00Z",
        },
      ]);
    const { container } = render(withClient(<MyTickets />));
    expect(await screen.findByText("Cannot play")).toBeInTheDocument();
    expect(screen.getByText("Waiting for you")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.queryByText("Old one")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Done · 1" }));
    expect(screen.getByText("Old one")).toBeInTheDocument();
    expect(screen.getByText("Resolved")).toBeInTheDocument();
    await expectAccessible(container);
  });
});
