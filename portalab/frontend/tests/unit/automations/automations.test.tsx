import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 019 / 027 — the builder offers the catalog (events grouped, a field per declared parameter) and lists the
// server's validation problems; runs show their status in text and, opened, each condition and step;
// approvals are approved from the inbox; a template opens the builder filled with it.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { Inbox } from "../../../src/features/automations/approvals/Inbox";
import { Editor } from "../../../src/features/automations/editor/Editor";
import { ExecutionList } from "../../../src/features/automations/history/ExecutionList";
import { Gallery } from "../../../src/features/automations/templates/Gallery";
import { json } from "../../support/fake-api";

const VARIABLE = ["$", "{event.campaign}"].join(""); // what the builder inserts

const CATALOG = {
  triggers: {
    events: ["campaign.started", "ticket.created"],
    schedules: ["at", "relative", "recurring"],
    event_fields: { "campaign.started": ["campaign", "occurrence"] },
  },
  conditions: [{ key: "event_field", description: "x", params: {} }],
  actions: [
    {
      key: "communication.produce",
      description: "Send",
      permission: "p",
      params: { category: "string" },
      required: ["category"],
      sensitivity: "normal",
    },
  ],
};

function show(element: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter([{ path: "/", element }])} />
    </QueryClientProvider>,
  );
}

describe("automations", () => {
  it("builds from the catalog and shows validation problems", async () => {
    const bodies: unknown[] = [];
    fake.handler = async (request) => {
      if (request.method === "GET") return json(200, CATALOG);
      bodies.push(await request.json());
      return json(422, {
        code: "automation.invalid_definition",
        title: "Invalid",
        errors: ["steps.step_1: missing params ['template_key']"],
      });
    };
    show(<Editor />);
    await screen.findByRole("option", { name: "A campaign starts" });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Announce campaigns" } });
    fireEvent.change(screen.getByLabelText("Event type"), { target: { value: "campaign.started" } });
    fireEvent.change(screen.getByLabelText("Action"), { target: { value: "communication.produce" } });
    // a field per declared parameter, and the event's variables a click puts into it
    const category = screen.getByLabelText("Category *");
    fireEvent.focus(category);
    fireEvent.click(screen.getByRole("button", { name: VARIABLE }));
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByText("steps.step_1: missing params ['template_key']")).toBeTruthy();
    expect(bodies[0]).toMatchObject({
      key: "announce_campaigns",
      definition: {
        trigger: { kind: "event", event_type: "campaign.started" },
        steps: [{ action: "communication.produce", params: { category: VARIABLE } }],
      },
    });
  });

  it("lists executions with text statuses and opens each step", async () => {
    fake.handler = (request) => {
      if (new URL(request.url).pathname.endsWith("/catalog")) return json(200, CATALOG);
      return json(200, [
        {
          id: "e1",
          automation_id: "a1",
          version: 1,
          status: "no_op",
          trigger_ref: { type: "campaign.started" },
          chain_id: "c",
          depth: 0,
          conditions_trace: [{ leaf: "event_field", result: false }],
          steps: [],
          batch_count: 1,
          error_code: null,
          started_at: "2026-10-01T12:00:00Z",
          finished_at: "2026-10-01T12:00:00Z",
        },
      ]);
    };
    show(<ExecutionList automationId="a1" />);
    const entry = await screen.findByRole("button", { name: /Conditions not met/ });
    fireEvent.click(entry);
    expect(screen.getByText(/Conditions not met — nothing ran/)).toBeTruthy();
    expect(screen.getByText(/A field of the event — not met/)).toBeTruthy();
  });

  it("approves from the inbox and opens a template in the builder", async () => {
    const posts: string[] = [];
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      if (request.method === "POST") {
        posts.push(path);
        return json(200, { status: "success" });
      }
      if (path.endsWith("/catalog")) return json(200, CATALOG);
      if (path.endsWith("/approvals"))
        return json(200, [
          {
            id: "ap1",
            execution_id: "e1",
            step_id: "w",
            action: "incident.create",
            summary: "Declare an incident",
            status: "pending",
            created_at: "2026-10-01T12:00:00Z",
            expires_at: "2026-10-04T12:00:00Z",
          },
        ]);
      return json(200, [
        { key: "weekly-digest", title: "Weekly digest", description: "News", valid: true, errors: [] },
      ]);
    };
    show(
      <>
        <Inbox />
        <Gallery />
      </>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await waitFor(() => expect(posts).toEqual(["/api/v1/admin/automations/approvals/ap1/approve"]));
    expect(await screen.findByRole("link", { name: "Use template" })).toHaveAttribute(
      "href",
      "/admin/automations/new?template=weekly-digest",
    );
  });
});
