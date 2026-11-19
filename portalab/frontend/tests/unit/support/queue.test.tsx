import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// Issue 512 — the team's queue: the states still to handle carry their count as a badge, and each ticket
// tells who opened it, when, and who handles it (« Unassigned » otherwise).

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { Queue } from "../../../src/features/support/staff/Queue";
import { json } from "../../support/fake-api";

const card = (n: number, title: string, extra: Record<string, unknown>) => ({
  id: `t${n}`,
  number: n,
  reference: `T-${String(n).padStart(6, "0")}`,
  title,
  type_key: "question",
  state: "open",
  priority: "normal",
  requester_id: "u1",
  assignee_id: null,
  incident_id: null,
  service_id: null,
  updated_at: "2026-11-19T16:59:00Z",
  created_at: "2026-11-19T16:58:00Z",
  requester_name: "Clément",
  assignee_name: null,
  ...extra,
});

function renderQueue() {
  fake.handler = (request) => {
    const path = new URL(request.url).pathname;
    if (path === "/api/v1/support/tickets/counts")
      return json(200, { states: { open: 4, in_progress: 1, closed: 9 } });
    if (path === "/api/v1/support/tickets")
      return json(200, {
        items: [
          card(16, "Marche pas", {}),
          card(15, "Birn", { assignee_id: "a1", assignee_name: "Jérémie" }),
        ],
        next_cursor: null,
      });
    return json(404, {});
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider
        router={createMemoryRouter([{ path: "/support/queue", element: <Queue /> }], {
          initialEntries: ["/support/queue"],
        })}
      />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("the support queue", () => {
  it("counts the states still to handle on their tabs", async () => {
    renderQueue();
    const states = await screen.findByRole("group");
    expect(await within(states).findByText("4")).toBeTruthy();
    expect(within(states).getByText("1")).toBeTruthy();
    expect(within(states).queryByText("9")).toBeNull(); // closed tickets carry no badge
  });

  it("tells who opened each ticket, when, and who handles it", async () => {
    renderQueue();
    const list = await screen.findByRole("list", { name: "Support queue" });
    const [loose, taken] = within(list).getAllByRole("listitem");
    expect(loose?.textContent).toContain("Opened by Clément");
    expect(loose?.textContent).toContain("Unassigned");
    expect(taken?.textContent).toContain("Jérémie");
  });
});
