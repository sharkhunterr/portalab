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
          { panel: "health", state: "unavailable", data: {} },
        ],
        required_actions: [{ id: "a", title_key: "Renew certificate", link: "/x", actionable: true }],
      });
    const { container } = render(withClient(<ControlCenter />));
    expect(await screen.findByText("active_policies")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Renew certificate" })).toBeInTheDocument();
    await expectAccessible(container);
  });

  it("configuration editor previews before applying and hides sensitive values", async () => {
    fake.handler = (request) => {
      const url = new URL(request.url);
      if (url.pathname.endsWith("/validate")) {
        return json(200, {
          ok: true,
          diff: [{ key: "demo.pageSize", before: 20, after: 50 }],
          warnings: [],
          errors: [],
        });
      }
      if (request.method === "PUT") return json(200, { applied: true });
      return json(200, {
        settings: [
          { key: "demo.pageSize", description: "Rows", sensitive: false, value: 20, source: "default" },
          { key: "demo.apiToken", description: "Token", sensitive: true, value: "***", source: "global" },
        ],
        policies: [],
      });
    };
    const { container } = render(withClient(<ConfigEditor />));
    expect(await screen.findByText("Hidden (write-only)")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("New value for demo.pageSize"), { target: { value: "50" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Preview the change" })[0] as HTMLElement);
    fireEvent.click(await screen.findByRole("button", { name: "Apply" }));
    expect(await screen.findByText("Configuration updated.")).toBeInTheDocument();
    await expectAccessible(container);
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
