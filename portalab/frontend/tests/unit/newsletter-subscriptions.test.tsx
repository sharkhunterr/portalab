import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Issue 326: a member's newsletters — the automatic ones first, each with when it goes out, left one by one;
// a newsletter whose channel was left is off with it.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { NewsletterSubscriptions } from "../../src/features/news/NewsletterSubscriptions";
import { json } from "../support/fake-api";

const LIST = [
  {
    key: "auto:1",
    kind: "automatic",
    name: "Hebdo n°3",
    description: "every Friday at 18:00",
    icon: "sparkles",
    channel: "club",
    subscribed: true,
  },
  {
    key: "auto:2",
    kind: "automatic",
    name: "Les sorties",
    description: "every day at 9:00",
    icon: "sparkles",
    channel: "films",
    subscribed: false,
  },
  {
    key: "club",
    kind: "channel",
    name: "Club",
    description: "",
    icon: null,
    channel: null,
    subscribed: true,
  },
  {
    key: "films",
    kind: "channel",
    name: "Films",
    description: "",
    icon: null,
    channel: null,
    subscribed: false,
  },
];

describe("issue 326 — my newsletters", () => {
  it("shows each automatic newsletter with when it goes out, and leaves one", async () => {
    const changes: unknown[] = [];
    fake.handler = async (request) => {
      if (request.method === "PUT") {
        changes.push(await request.json());
        return json(200, LIST);
      }
      return json(200, LIST);
    };
    render(
      <QueryClientProvider client={new QueryClient()}>
        <NewsletterSubscriptions />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Every Friday at 18:00")).toBeInTheDocument();
    expect(screen.getByText("Automatic newsletters")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Les sorties" })).toBeDisabled(); // its channel left
    expect(screen.getByText(/Off with its channel « Films »/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("switch", { name: "Hebdo n°3" }));
    await waitFor(() => expect(changes).toEqual([{ changes: { "auto:1": false } }]));
  });
});
