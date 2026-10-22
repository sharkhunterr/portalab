import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 016 T025/T028/T030/T034 — the new-ticket flow surfaces open incidents and wiki pages before the form,
// names missing required fields, links the chosen incident; feedback conversions unavailable in this
// installation are disabled with their reason; diagnosis events are parsed into labelled steps.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { ReviewQueue } from "../../../src/features/support/feedback/ReviewQueue";
import { parseEvents } from "../../../src/features/support/tickets/DiagnosisPanel";
import { NewTicket } from "../../../src/features/support/tickets/NewTicket";
import { json } from "../../support/fake-api";

function renderAt(path: string, routes: Array<{ path: string; element: ReactNode }>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("new ticket", () => {
  it("prechecks, names missing fields and links the incident", async () => {
    const posted: Array<Record<string, unknown>> = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/tickets/types")
        return json(200, [
          {
            key: "bug",
            label: "Something is broken",
            fields: [{ key: "steps", label: "What did you do?", type: "long_text", required: true }],
          },
        ]);
      if (path === "/api/v1/tickets/precheck")
        return json(200, {
          incidents: {
            state: "ok",
            items: [
              {
                id: "i1",
                reference: "INC-0001",
                title: "Media down",
                severity: "major",
                state: "identified",
                url: "/incidents/i1",
              },
            ],
          },
          knowledge: { state: "unavailable", items: [] },
        });
      if (path === "/api/v1/tickets" && request.method === "POST") {
        posted.push((await request.json()) as Record<string, unknown>);
        return json(422, {
          code: "ticket.required_fields_missing",
          title: "Required fields are missing",
          fields: ["steps"],
        });
      }
      return json(404, {});
    };
    renderAt("/support/new", [{ path: "/support/new", element: <NewTicket /> }]);
    await screen.findByRole("option", { name: "Something is broken" });
    fireEvent.change(screen.getByLabelText("Kind of request"), { target: { value: "bug" } });
    fireEvent.change(screen.getByLabelText("Describe the problem"), {
      target: { value: "Media will not play" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check first" }));
    expect(await screen.findByRole("link", { name: "INC-0001 · Media down" })).toBeTruthy();
    expect(screen.getByText("Wiki suggestions are not available right now.")).toBeTruthy();
    fireEvent.click(screen.getByLabelText("My problem is this incident"));
    fireEvent.change(screen.getByLabelText("Title *"), { target: { value: "Cannot play" } });
    fireEvent.click(screen.getByRole("button", { name: "Open the ticket" }));
    await waitFor(() => expect(posted).toHaveLength(1));
    expect(await screen.findByText("Fill in: steps")).toBeTruthy();
    expect(posted[0]).toMatchObject({ type_key: "bug", title: "Cannot play", incident_id: "i1" });
  });
});

describe("feedback review", () => {
  it("disables unavailable conversions with their reason", async () => {
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/support/feedback")
        return json(200, [
          {
            id: "f1",
            form_key: "bug_report",
            form_version: 1,
            kind: "bug_report",
            status: "new",
            payload: { what: "slow" },
            submitter_id: null,
            created_at: "2026-10-01T00:00:00Z",
          },
        ]);
      return json(200, {
        id: "f1",
        form_key: "bug_report",
        form_version: 1,
        kind: "bug_report",
        status: "new",
        payload: { what: "slow" },
        submitter_id: null,
        created_at: "2026-10-01T00:00:00Z",
        conversions: [
          { target: "ticket", available: true, reason: null, done: null },
          { target: "feature_proposal", available: false, reason: "community_unavailable", done: null },
        ],
      });
    };
    renderAt("/", [{ path: "/", element: <ReviewQueue /> }]);
    fireEvent.click(await screen.findByRole("button", { name: /A member.*bug_report/ }));
    // the ticket is a big action of its own; the other conversions wait in « More »
    await waitFor(() =>
      expect((screen.getByRole("button", { name: /Make a ticket/ }) as HTMLButtonElement).disabled).toBe(
        false,
      ),
    );
    fireEvent.keyDown(screen.getByRole("button", { name: /^More$/ }), { key: "Enter" });
    const proposal = await screen.findByRole("menuitem", { name: /Feature proposal/ });
    expect(proposal.getAttribute("aria-disabled")).toBe("true");
    expect(proposal.textContent).toContain("Community is not available");
  });
});

describe("diagnosis stream", () => {
  it("parses labelled steps", () => {
    const raw =
      'event: step\ndata: {"name":"identify_user","kind":"real","status":"ok","data":{}}\n\n' +
      'event: step\ndata: {"name":"analyze","kind":"ai","status":"ok","data":{"summary":"overloaded"}}\n\n' +
      'event: done\ndata: {"done":true,"draft":"d1"}\n\n';
    expect(parseEvents(raw).map((e) => [e.event, e.data.kind ?? e.data.draft])).toEqual([
      ["step", "real"],
      ["step", "ai"],
      ["done", "d1"],
    ]);
  });
});
