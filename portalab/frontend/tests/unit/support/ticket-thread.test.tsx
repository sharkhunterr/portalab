import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// Issue 510 — the ticket's thread tells the team whom the ticket went to, who handed it over when someone
// else did, and when an automation did it; a member keeps reading « Assignment » (never who in the team).

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { TicketPage } from "../../../src/features/support/tickets/TicketPage";
import { json } from "../../support/fake-api";

const ME = "00000000-0000-7000-8000-00000000000a";
const SAM = "00000000-0000-7000-8000-00000000000b";
const URSULA = "00000000-0000-7000-8000-00000000000c";

function ticket(staff: boolean, people: Record<string, string>) {
  return {
    id: "t1",
    number: 14,
    reference: "T-000014",
    title: "On test",
    type_key: "question",
    state: "open",
    priority: "normal",
    requester_id: URSULA,
    assignee_id: SAM,
    incident_id: null,
    service_id: null,
    updated_at: "2026-11-19T16:02:00Z",
    description: "Testsded",
    fields: {},
    field_defs: [],
    tags: [],
    version: 4,
    source: "manual",
    state_label: "Open",
    incident_reference: null,
    feedback: null,
    comments: [],
    attachments: [],
    history: [
      {
        seq: 1,
        kind: "created",
        actor_id: URSULA,
        data: { type: "question" },
        created_at: "2026-11-19T16:01:00Z",
      },
      {
        seq: 2,
        kind: "assignment",
        actor_id: ME,
        data: { from: null, to: ME, via: "automation" },
        created_at: "2026-11-19T16:01:05Z",
      },
      {
        seq: 3,
        kind: "assignment",
        actor_id: ME,
        data: { from: ME, to: SAM },
        created_at: "2026-11-19T16:01:10Z",
      },
      {
        seq: 4,
        kind: "assignment",
        actor_id: SAM,
        data: { from: SAM, to: null },
        created_at: "2026-11-19T16:01:20Z",
      },
    ],
    transitions: [],
    staff,
    people,
  };
}

function renderTicket(body: Record<string, unknown>, team: boolean, me: string) {
  fake.handler = (request) => {
    const path = new URL(request.url).pathname;
    if (path === "/api/v1/me") return json(200, { id: me, display_name: "Me", permissions: [] });
    if (path === "/api/v1/tickets/t1") return json(200, body);
    return json(404, {});
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider
        router={createMemoryRouter([{ path: "/tickets/:ticketId", element: <TicketPage team={team} /> }], {
          initialEntries: ["/tickets/t1"],
        })}
      />
    </QueryClientProvider>,
  );
}

const lines = () => [...document.querySelectorAll(".feedback-event")].map((li) => li.textContent ?? "");

afterEach(cleanup);

describe("a ticket's thread", () => {
  it("tells the team whom it went to, by whom, and when an automation did it", async () => {
    renderTicket(ticket(true, { [SAM]: "Sam", [URSULA]: "Ursula", [ME]: "Me" }), true, ME);
    await screen.findByRole("heading", { name: "On test" });
    const [, auto, handed, dropped] = lines();
    expect(auto).toContain("Assigned to you · by an automation");
    expect(handed).toContain("Assigned to Sam by you");
    expect(dropped).toContain("Unassigned");
  });

  it("keeps the team anonymous to the member", async () => {
    renderTicket(ticket(false, {}), false, URSULA);
    await screen.findByRole("heading", { name: "On test" });
    const [, auto, handed] = lines();
    expect(auto).toContain("Assignment · by an automation");
    expect(handed).toContain("Assignment");
    expect(handed).not.toContain("Sam");
  });
});
