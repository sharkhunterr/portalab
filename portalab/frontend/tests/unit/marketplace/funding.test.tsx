import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 015 T014 — the funding panel states the frozen rules and the non-guarantee notice; Coins can only be
// reserved once the notice is acknowledged; the request carries an idempotency key. Issue 304: where the
// funding stands (gathered, the goal, what is left) and quick amounts up to what I may still give.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { FundingPanel, FundingProgress } from "../../../src/features/marketplace/projects/FundingPanel";
import { json } from "../../support/fake-api";

const PROJECT = {
  id: "p1",
  proposal_ref: "pr1",
  title: "Dark mode",
  state: "open",
  accepts_votes: true,
  accepts_funding: true,
  funding_rules: { consume_at: "released", min_funding: 5, max_funding_per_user: 200, refund_on_reject: 100 },
  rules_frozen_at: "2026-10-01T12:00:00Z",
  version: 3,
  updated_at: "2026-10-01T12:00:00Z",
  totals: { reserved: 60, consumed: 0, funders: 1, goal_amount: null },
  history: [],
  notes: [],
};

function show(element: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter([{ path: "/", element }])} />
    </QueryClientProvider>,
  );
}

describe("funding panel", () => {
  it("requires the acknowledgement and sends an idempotency key", async () => {
    const requests: Request[] = [];
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/me/permissions") {
        return json(200, { permissions: ["marketplace.purchase"], roles: ["user"] });
      }
      requests.push(request.clone());
      return json(201, { id: "f1", project_id: "p1", amount: 20, status: "reserved" });
    };
    show(<FundingPanel project={PROJECT as never} mine={150} />);
    expect(await screen.findByText(/does not guarantee that the project will be built/)).toBeTruthy();
    expect(screen.getByText("Reserved Coins are used when the project is released.")).toBeTruthy();
    // 150 of the 200 a member may give already given: the quick amounts stop at the 50 left
    expect(screen.getByRole("button", { name: "Max · 50" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "100" })).toBeNull();
    fireEvent.change(await screen.findByLabelText("Coins to reserve"), { target: { value: "20" } });
    const submit = screen.getByRole("button", { name: "Reserve Coins" });
    expect((submit as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText(/I understand that funding/));
    expect((submit as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(submit);
    await waitFor(() => expect(requests).toHaveLength(1));
    expect(requests[0]?.headers.get("Idempotency-Key")).toBeTruthy();
    expect(await requests[0]?.json()).toEqual({ amount: 20, acknowledged: true });
  });
});

describe("funding progress", () => {
  it("tells what is gathered, toward the goal, and what is left", () => {
    show(
      <FundingProgress
        project={{ ...PROJECT, totals: { ...PROJECT.totals, goal_amount: 500 } } as never}
        mine={20}
      />,
    );
    expect(screen.getAllByText("60")).toHaveLength(2); // gathered, and reserved
    expect(screen.getByText("440 Coins left to gather")).toBeTruthy();
  });

  it("says when the goal is reached, and when there is none", () => {
    show(
      <FundingProgress
        project={{ ...PROJECT, totals: { ...PROJECT.totals, goal_amount: 50 } } as never}
        mine={0}
      />,
    );
    expect(screen.getByText("Goal reached!")).toBeTruthy();
  });
});
