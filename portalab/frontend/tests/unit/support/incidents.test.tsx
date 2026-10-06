import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 016 T013 — banner for open incidents (silent otherwise); list/detail with the public timeline rendered as
// text; the console posts updates with If-Match and reports a concurrent change.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { AnnounceProvider } from "../../../src/design-system/a11y/Announce";
import { IncidentBanner } from "../../../src/features/support/incidents/IncidentBanner";
import { IncidentConsole } from "../../../src/features/support/incidents/IncidentConsole";
import { IncidentsPage } from "../../../src/features/support/incidents/IncidentsPage";
import { json } from "../../support/fake-api";

const INCIDENT = {
  id: "0190f0a0-0000-7000-8000-0000000000aa",
  reference: "INC-0007",
  title: "<b>Media</b> down",
  summary: "Playback fails.",
  severity: "critical",
  state: "identified",
  source: "manual",
  created_at: "2026-10-05T10:00:00Z",
  updated_at: "2026-10-05T11:00:00Z",
  resolved_at: null,
  version: 3,
  services: [{ id: "s1", name: "Media" }],
  updates: [
    {
      seq: 1,
      state: "investigating",
      severity: "critical",
      message: "Looking into it.",
      at: "2026-10-05T10:00:00Z",
      author_user_id: null,
    },
    {
      seq: 2,
      state: "identified",
      severity: "critical",
      message: "Disk full.",
      at: "2026-10-05T11:00:00Z",
      author_user_id: null,
    },
  ],
  evidence: [],
};

function renderAt(path: string, routes: Array<{ path: string; element: ReactNode }>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AnnounceProvider>
        <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
      </AnnounceProvider>
    </QueryClientProvider>,
  );
}

describe("incidents", () => {
  it("shows a banner only while incidents are open", async () => {
    fake.handler = () => json(200, [INCIDENT]);
    renderAt("/", [{ path: "/", element: <IncidentBanner /> }]);
    expect(await screen.findByRole("link", { name: "INC-0007 · <b>Media</b> down" })).toBeTruthy();
    expect(document.querySelector("b")).toBeNull();
  });

  it("renders the detail timeline as text, newest first", async () => {
    fake.handler = () => json(200, INCIDENT);
    renderAt(`/incidents/${INCIDENT.id}`, [{ path: "/incidents/:incidentId", element: <IncidentsPage /> }]);
    await screen.findByRole("heading", { name: "<b>Media</b> down" }); // text, never markup
    expect(screen.getByText("INC-0007")).toBeTruthy();
    const items = [...document.querySelectorAll(".incident-timeline > li")].map((li) => li.textContent ?? "");
    expect(items[0]).toContain("Disk full."); // newest first
    expect(items.at(-1)).toContain("Incident declared");
    expect(screen.getByRole("link", { name: "Media" }).getAttribute("href")).toBe("/services/s1");
  });

  it("posts updates with If-Match and reports conflicts", async () => {
    const writes: Array<{ path: string; ifMatch: string | null }> = [];
    let conflict = false;
    fake.handler = (request) => {
      const url = new URL(request.url);
      if (request.method === "GET") return json(200, [INCIDENT]);
      writes.push({ path: url.pathname, ifMatch: request.headers.get("If-Match") });
      return conflict
        ? json(409, { code: "incident.version_conflict", title: "Conflict" })
        : json(200, INCIDENT);
    };
    renderAt("/admin/incidents", [{ path: "/admin/incidents", element: <IncidentConsole /> }]);
    await screen.findByRole("heading", { name: "INC-0007 · <b>Media</b> down" });
    fireEvent.change(screen.getByLabelText("Public update"), { target: { value: "Fix deployed." } });
    fireEvent.click(screen.getByRole("button", { name: "Post update" }));
    await waitFor(() =>
      expect(writes[0]).toEqual({ path: `/api/v1/admin/incidents/${INCIDENT.id}/updates`, ifMatch: "3" }),
    );
    conflict = true;
    fireEvent.click(screen.getByRole("button", { name: "Resolve" }));
    expect(await screen.findByText(/changed meanwhile/)).toBeTruthy();
  });
});
