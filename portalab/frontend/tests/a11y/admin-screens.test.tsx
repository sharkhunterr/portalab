import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

// 020 T030 — Control Center, configuration editor (preview → apply), toggles, first-run wizard: explicit
// states, keyboard-operable native controls, no axe violations.

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
import { ConfigEditor, ControlCenter, FirstRunWizard, Toggles } from "../../src/features/admin";
import { json } from "../support/fake-api";

function withClient(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={client}>
      <main>{children}</main>
    </QueryClientProvider>
  );
}

async function expectAccessible(container: HTMLElement) {
  const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  expect(results.violations.map((violation) => violation.id)).toEqual([]);
}

describe("admin screens", () => {
  it("Control Center renders each panel with its own state", async () => {
    fake.handler = () =>
      json(200, {
        panels: [
          { panel: "configuration", state: "available", data: { active_policies: 1 } },
          { panel: "storage", state: "unavailable", data: {} },
          {
            panel: "services",
            state: "partial",
            data: { total: 3, troubled: 1, by_state: { ok: 2, degraded: 1 } },
          },
          { panel: "custom_panel", state: "available", data: { open_items: 4 } },
        ],
        required_actions: [
          { id: "a", title_key: "Renew certificate", link: "/x", actionable: true, impact: 5 },
        ],
      });
    const { container } = render(withClient(<MemoryRouter>{<ControlCenter />}</MemoryRouter>));
    expect(await screen.findByText("Active policies")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByText("Open items")).toBeInTheDocument();
    expect(screen.getByText("Degraded · 1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Renew certificate" })).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add a service" })).toHaveAttribute(
      "href",
      "/admin/services?add=1",
    );
    await expectAccessible(container);
  });

  it("configuration editor validates before applying, in place, and hides sensitive values", async () => {
    const calls: string[] = [];
    fake.handler = (request) => {
      const url = new URL(request.url);
      if (url.pathname.endsWith("/validate")) {
        calls.push("validate");
        return json(200, {
          ok: true,
          diff: [{ key: "demo.pageSize", before: 20, after: 50 }],
          warnings: [],
          errors: [],
        });
      }
      if (request.method === "PUT") {
        calls.push("apply");
        return json(200, { applied: true });
      }
      return json(200, {
        settings: [
          {
            key: "demo.pageSize",
            description: "Rows",
            sensitive: false,
            value: 20,
            source: "default",
            kind: "integer",
          },
          {
            key: "demo.apiToken",
            description: "Token",
            sensitive: true,
            value: "***",
            source: "global",
            kind: "string",
          },
          {
            key: "demo.enabled",
            description: "Enabled",
            sensitive: false,
            value: true,
            source: "default",
            kind: "boolean",
          },
        ],
        policies: [],
      });
    };
    const { container } = render(withClient(<ConfigEditor />));
    expect(await screen.findByText("Hidden (write-only)")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Enabled" })).toBeChecked();
    await expectAccessible(container);
    fireEvent.change(screen.getByLabelText("Rows"), { target: { value: "50" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Configuration updated. (20 → 50)")).toBeInTheDocument();
    expect(calls).toEqual(["validate", "apply"]); // checked by the server first, then applied
  });

  it("toggles explain refusals", async () => {
    fake.handler = () => json(409, { code: "admin.enable_refused" });
    const { container } = render(withClient(<Toggles />));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "weather" } });
    fireEvent.click(screen.getByRole("button", { name: "Enable" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("cannot be enabled");
    await expectAccessible(container);
  });

  it("first-run wizard and its closed state", async () => {
    fake.handler = (request) =>
      request.method === "GET"
        ? json(200, { completed: false, steps: [{ step: "services", skippable: true }] })
        : json(201, {});
    const { container } = render(withClient(<FirstRunWizard />));
    expect(await screen.findByRole("heading", { name: "Set up your portal" })).toBeInTheDocument();
    await expectAccessible(container);
    fake.handler = () => json(200, { completed: true, steps: [] });
    render(withClient(<FirstRunWizard />));
    expect(await screen.findByText("The portal is already set up.")).toBeInTheDocument();
  });
});
