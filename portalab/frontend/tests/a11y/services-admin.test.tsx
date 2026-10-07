import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

// 005 T034 — services admin: list with states, configure + test (write-only secret), enable, disconnect
// confirmation, sync history; keyboard-operable buttons and accessible states.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));

vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { MemoryRouter } from "react-router";
import { ServicesAdmin } from "../../src/features/admin";
import { json } from "../support/fake-api";

function withClient(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <main>{children}</main>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const SERVICE = {
  id: "s1",
  connector: "fake",
  name: "Media server",
  state: "enabled",
  display_state: "enabled",
  health: "closed",
  stale: false,
  sync: { status: "idle", last_success_at: null },
};

describe("services admin", () => {
  it("configures, tests, acts on a service and shows its history", async () => {
    const calls: string[] = [];
    let savedBody: Record<string, unknown> = {};
    fake.handler = async (request) => {
      const url = new URL(request.url);
      calls.push(`${request.method} ${url.pathname}`);
      if (url.pathname === "/api/v1/connectors") {
        return json(200, {
          items: [
            {
              key: "fake",
              name: "Fake service",
              secret_fields: ["api_token"],
              config_schema: {
                properties: { base_url: { type: "string", title: "Base Url" } },
                required: ["base_url"],
              },
              compatibility: { result: "compatible", reasons: [] },
            },
          ],
        });
      }
      if (url.pathname === "/api/v1/services" && request.method === "GET") {
        return json(200, { items: [SERVICE] });
      }
      if (url.pathname === "/api/v1/connectors/fake/test") {
        return json(200, { ok: false, detail: "Cannot reach the service." });
      }
      if (url.pathname === "/api/v1/services" && request.method === "POST") {
        savedBody = (await request.json()) as Record<string, unknown>;
        return json(201, { ...SERVICE, id: "s2", state: "configured" });
      }
      if (url.pathname.endsWith("/sync-runs")) {
        return json(200, {
          items: [
            {
              id: "r1",
              kind: "manual",
              status: "succeeded",
              added: 3,
              modified: 1,
              removed: 0,
              errored: 0,
              last_error: null,
            },
          ],
        });
      }
      if (url.pathname.endsWith("/sync")) {
        return json(202, { job_id: "j1", queued: true });
      }
      return json(200, { ...SERVICE, state: "disconnected", display_state: "disconnected" });
    };
    const { container } = render(withClient(<ServicesAdmin />));
    expect(await screen.findByText("Media server")).toBeInTheDocument();
    expect(screen.getByText("Enabled", { selector: ".status-badge" })).toBeInTheDocument();
    expect(screen.getByText(/Never synchronized/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Add a service" }));
    const dialog = await screen.findByRole("dialog", { name: "Add a service" });
    fireEvent.click(await within(dialog).findByRole("button", { name: /Fake service/ }));
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "Home" } });
    fireEvent.change(within(dialog).getByLabelText("Address"), { target: { value: "http://media.lan" } });
    const secret = within(dialog).getByLabelText("API token");
    expect(secret).toHaveAttribute("type", "password");
    fireEvent.change(secret, { target: { value: "s3cret" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Test the connection" }));
    expect(
      await within(dialog).findByText("Connection failed: Cannot reach the service."),
    ).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(await within(dialog).findByText(/Service saved/)).toBeInTheDocument();
    expect(savedBody).toMatchObject({
      connector: "fake",
      name: "Home",
      config: { base_url: "http://media.lan" },
    });
    expect((within(dialog).getByLabelText("API token") as HTMLInputElement).value).toBe(""); // never kept
    fireEvent.keyDown(dialog, { key: "Escape" });
    await vi.waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Sync now" }));
    expect(await screen.findByText("Synchronization queued.")).toBeInTheDocument();
    // 027: the less frequent actions are in the card's « … » menu
    const more = () =>
      fireEvent.keyDown(screen.getByRole("button", { name: /More actions for/ }), { key: "Enter" });
    more();
    fireEvent.click(await screen.findByRole("menuitem", { name: "Sync history" }));
    expect(await screen.findByText(/manual · succeeded · \+3 ~1 -0/)).toBeInTheDocument();
    fireEvent.keyDown(await screen.findByRole("dialog"), { key: "Escape" });
    await vi.waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    more();
    fireEvent.click(await screen.findByRole("menuitem", { name: "Disconnect" }));
    expect(calls.some((call) => call.endsWith("/disconnect"))).toBe(false);
    fireEvent.click(await screen.findByRole("button", { name: "Confirm disconnection (data is kept)" }));
    await vi.waitFor(() => expect(calls.some((call) => call.endsWith("/disconnect"))).toBe(true));

    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });
});
