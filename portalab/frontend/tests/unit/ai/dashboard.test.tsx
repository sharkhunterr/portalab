import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// Issue 176 — the administrators' view of the assistant: key figures, who uses it, its tools and the
// answers rated « not as expected » with their question and the member's comment.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { AiDashboard } from "../../../src/features/ai/admin/AiDashboard";
import { json } from "../../support/fake-api";

const BOARD = {
  days: 30,
  totals: {
    questions: 4,
    members: 2,
    answered: 3,
    errors: 1,
    unanswered: 0,
    sourced: 3,
    nudged: 1,
    latency_median_ms: 4200,
    latency_p90_ms: 9100,
    tokens_per_answer: 2500,
    rated_up: 1,
    rated_down: 1,
  },
  errors: [{ code: "ai.unavailable", count: 1 }],
  models: [{ model: "qwen3:8b", answers: 4 }],
  per_day: [{ day: "2026-10-20", questions: 4, members: 2, errors: 1 }],
  hours_utc: Array.from({ length: 24 }, (_, hour) => (hour === 12 ? 4 : 0)),
  members: [{ user_id: "u1", name: "Ursula", questions: 3, last_at: "2026-10-20T12:00:00Z" }],
  tools: [{ name: "media.status", calls: 3, failed: 1 }],
  rated_down: [
    {
      message_id: "m1",
      member: "Ursula",
      at: "2026-10-20T12:05:00Z",
      comment: "The menu moved.",
      question: "How do I change my avatar?",
      answer: "Open your account.",
      tools: ["media.status"],
      error: null,
    },
  ],
};

describe("AiDashboard", () => {
  it("shows the figures, the members, the tools and the answers rated down", async () => {
    fake.handler = (request) =>
      new URL(request.url).pathname === "/api/v1/admin/ai/dashboard" ? json(200, BOARD) : json(404, {});
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const router = createMemoryRouter([{ path: "/", element: <AiDashboard /> }], { initialEntries: ["/"] });
    render(
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("How do I change my avatar?")).toBeTruthy();
    expect(screen.getByText("The menu moved.")).toBeTruthy();
    expect(screen.getByText("75%")).toBeTruthy(); // answered: 3 of 4
    expect(screen.getByText("4.2 s")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Ursula" }).getAttribute("href")).toBe("/community/members/u1");
    expect(screen.getByText("qwen3:8b")).toBeTruthy();
    expect(screen.getByText("Provider not answering")).toBeTruthy();
  });
});
