import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// Issue 354: a media's open reports — a beating badge in its head, their list at the bottom, the closed ones
// on demand.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import {
  MediaTickets,
  MediaTicketsBadge,
  PosterTickets,
} from "../../src/features/support/tickets/MediaTickets";
import { json } from "../support/fake-api";

const AT = "2027-01-10T10:00:00Z";
const ticket = (id: string, title: string, open: boolean, mine: boolean) => ({
  id,
  reference: `T-00000${id}`,
  title,
  state: open ? "open" : "resolved",
  open,
  mine,
  created_at: AT,
  updated_at: AT,
});

function show() {
  const asked: string[] = [];
  fake.handler = (request) => {
    const url = new URL(request.url);
    if (url.pathname !== "/api/v1/tickets/media/m-1") return json(200, []);
    const closed = url.searchParams.get("closed") === "true";
    asked.push(String(closed));
    const items = [
      ticket("1", "Sound — “Alien”", true, true),
      ticket("2", "Subtitles — “Alien”", true, false),
    ];
    return json(200, {
      open: 2,
      closed: 1,
      staff: false,
      items: closed ? [...items, ticket("3", "Picture — “Alien”", false, false)] : items,
    });
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <MediaTicketsBadge mediaId="m-1" />
        <MediaTickets mediaId="m-1" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return asked;
}

describe("a media's reports", () => {
  it("beats a badge while some are open and lists them, the closed ones on demand", async () => {
    const asked = show();
    const badge = await screen.findByRole("link", { name: /2 open reports/ });
    expect(badge.getAttribute("href")).toBe("#media-tickets");
    expect(await screen.findByRole("link", { name: /Sound — “Alien”/ })).toBeTruthy(); // mine: opens it
    expect(screen.getByText("Subtitles — “Alien”").closest("a")).toBeNull(); // another's: title only
    expect(screen.queryByText("Picture — “Alien”")).toBeNull();
    fireEvent.click(screen.getByRole("checkbox", { name: /Show the closed report too/ }));
    expect(await screen.findByText("Picture — “Alien”")).toBeTruthy();
    expect(asked).toContain("true");
  });

  it("flags a poster with its open reports, how many when more than one", async () => {
    fake.handler = (request) =>
      new URL(request.url).pathname === "/api/v1/media-tickets/open"
        ? json(200, { "m-1": 2, "m-2": 1 })
        : json(200, {});
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <PosterTickets mediaId="m-1" />
        <PosterTickets mediaId="m-2" />
        <PosterTickets mediaId="m-3" />
      </QueryClientProvider>,
    );
    const flags = await screen.findAllByRole("img", { name: /open report/ });
    expect(flags.map((f) => f.getAttribute("aria-label"))).toEqual(["2 open reports", "1 open report"]);
    expect(flags[0]?.textContent).toBe("2");
    expect(flags[1]?.textContent).toBe("");
  });
});
