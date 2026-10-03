import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 019 — the builder offers the catalog and lists the server's validation problems; executions show status
// in text with the condition trace; approvals are approved from the inbox; templates instantiate drafts.

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
import { Builder } from "../../../src/features/automations/builder/Builder";
import { ExecutionList } from "../../../src/features/automations/history/ExecutionList";
import { Gallery } from "../../../src/features/automations/templates/Gallery";
import { json } from "../../support/fake-api";

const CATALOG = {
  triggers: { events: ["campaign.started", "ticket.created"], schedules: ["at", "relative", "recurring"] },
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
        errors: ["steps.step_1: missing params ['category']"],
      });
    };
    show(<Builder />);
    await screen.findByRole("option", { name: "campaign.started" });
    fireEvent.change(screen.getByLabelText("Key"), { target: { value: "announce" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Announce" } });
    fireEvent.change(screen.getByLabelText("Event type"), { target: { value: "campaign.started" } });
    fireEvent.change(screen.getByLabelText("Action"), { target: { value: "communication.produce" } });
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByText("steps.step_1: missing params ['category']")).toBeTruthy();
    expect(bodies[0]).toMatchObject({
      key: "announce",
      definition: { trigger: { kind: "event", event_type: "campaign.started" } },
    });
  });

  it("lists executions with text statuses and traces", async () => {
    fake.handler = () =>
      json(200, [
        {
          id: "e1",
          automation_id: "a1",
          version: 1,
          status: "no_op",
          trigger_ref: {},
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
    show(<ExecutionList automationId="a1" />);
    const entry = await screen.findByRole("button", { name: /Conditions not met/ });
    fireEvent.click(entry);
    expect(screen.getByText("event_field — false")).toBeTruthy();
  });

  it("approves from the inbox and instantiates templates", async () => {
    const posts: string[] = [];
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      if (request.method === "POST") {
        posts.push(path);
        return json(200, { status: "success" });
      }
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
    fireEvent.click(await screen.findByRole("button", { name: "Use template" }));
    await waitFor(() =>
      expect(posts).toEqual([
        "/api/v1/admin/automations/approvals/ap1/approve",
        "/api/v1/admin/automations/templates/weekly-digest/instantiate",
      ]),
    );
  });
});
