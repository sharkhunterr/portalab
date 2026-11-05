import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// Issue 355: a title's reviews — a rating and a few words once seen; the others' signed or « Anonymous ».

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { Reviews } from "../../../src/features/media/detail/Reviews";
import { json } from "../../support/fake-api";

const AT = "2027-01-09T10:00:00Z";
const BASE = {
  object_id: "m-1",
  reviewable: true,
  can_review: true,
  count: 2,
  average: 3.5,
  mine: null,
  items: [
    { author_id: "u-2", author: "Alex", mine: false, rating: 4, comment: "Très bon", at: AT },
    { author_id: null, author: null, mine: false, rating: 3, comment: null, at: AT },
  ],
};

function show(view: Record<string, unknown>) {
  const sent: unknown[] = [];
  fake.handler = async (request) => {
    const url = new URL(request.url);
    if (url.pathname === "/api/v1/media/m-1/reviews/mine" && request.method === "PUT") {
      const body = (await request.json()) as { rating: number; comment: string | null };
      sent.push(body);
      return json(200, {
        ...view,
        count: 3,
        mine: { author_id: "me", author: "Moi", mine: true, ...body, at: AT },
      });
    }
    if (url.pathname === "/api/v1/media/m-1/reviews") return json(200, view);
    return json(200, []);
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Reviews objectId="m-1" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return sent;
}

describe("a title's reviews", () => {
  it("lists the others' reviews, signed or anonymous, and posts mine", async () => {
    const sent = show(BASE);
    expect(await screen.findByRole("link", { name: "Alex" })).toBeTruthy();
    expect(screen.getByText("Anonymous")).toBeTruthy();
    expect(screen.getByText(/3\.5 \/ 5 · 2 reviews/)).toBeTruthy();
    const submit = screen.getByRole("button", { name: "Post my review" }) as HTMLButtonElement;
    expect(submit.disabled).toBe(true); // a rating first
    fireEvent.click(screen.getByRole("radio", { name: "4 stars out of 5" }));
    fireEvent.change(screen.getByLabelText(/A word on this title/), { target: { value: "Superbe" } });
    fireEvent.click(submit);
    await vi.waitFor(() => expect(sent).toEqual([{ rating: 4, comment: "Superbe" }]));
    expect(await screen.findByText("My review")).toBeTruthy();
    expect(screen.getByText("Superbe")).toBeTruthy();
  });

  it("asks to watch it first, and shows nothing for a title that takes no review", async () => {
    show({ ...BASE, can_review: false, count: 0, average: null, items: [] });
    expect(await screen.findByText(/Watch, read, listen to or play this title/)).toBeTruthy();
  });
});
