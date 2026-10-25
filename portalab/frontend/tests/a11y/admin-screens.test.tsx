import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

// 020 T030 — Control Center, configuration editor (preview → apply), toggles, arrival wizard: explicit
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
import { ArrivalWizard, ConfigEditor, ControlCenter, Toggles } from "../../src/features/admin";
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
    // issue 14: a setting without a title of its own is an advanced one — shown with its technical key
    fireEvent.click(await screen.findByRole("checkbox", { name: /advanced settings/ }));
    expect(await screen.findByText("Hidden (write-only)")).toBeInTheDocument();
    expect(screen.getByText("demo.pageSize")).toBeInTheDocument();
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

  it("arrival wizard (issue 246): language, installation, features, administrator, then everything at once", async () => {
    const calls: Array<{ method: string; path: string; body: unknown }> = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      const body = request.method === "GET" ? null : await request.json().catch(() => null);
      calls.push({ method: request.method, path, body });
      if (path === "/api/v1/i18n/public/languages")
        return json(200, {
          default: "en",
          items: [
            { code: "en", name_native: "English", direction: "ltr" },
            { code: "fr", name_native: "Français", direction: "ltr" },
          ],
        });
      if (path.startsWith("/api/v1/i18n/public/catalogs/")) return json(200, { messages: {} });
      if (path === "/api/v1/admin/first-run")
        return request.method === "GET" ? json(200, { completed: false }) : json(201, {});
      if (path === "/api/v1/admin/modules")
        return json(200, [
          { key: "content", enabled: true, requires: [], essential: false, needs_restart: false },
          { key: "wiki", enabled: true, requires: ["content"], essential: false, needs_restart: false },
          { key: "news", enabled: true, requires: ["content"], essential: false, needs_restart: false },
        ]);
      return json(200, {});
    };
    const assign = vi.fn();
    vi.stubGlobal("location", {
      ...globalThis.location,
      assign,
      pathname: "/setup",
      origin: "https://portal.test",
    });
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const { container } = render(
      <QueryClientProvider client={client}>
        <ArrivalWizard />
      </QueryClientProvider>,
    );
    expect(await screen.findByRole("heading", { name: "Welcome to Portalab" })).toBeInTheDocument();
    // issue 247: importing another Portalab opens its own step (the archive, its passphrase)
    fireEvent.click(screen.getByRole("button", { name: /Import another Portalab/ }));
    fireEvent.click(screen.getByRole("button", { name: /Continue/ }));
    expect(await screen.findByLabelText("The archive's passphrase")).toBeInTheDocument();
    await expectAccessible(container);
    fireEvent.click(screen.getByRole("button", { name: /Back/ }));
    fireEvent.click(screen.getByRole("button", { name: /New installation/ }));
    await expectAccessible(container);
    fireEvent.click(screen.getByRole("button", { name: /Continue/ }));
    fireEvent.click(await screen.findByRole("checkbox", { name: /Wiki/ }));
    expect(screen.getByRole("checkbox", { name: /Wiki/ })).not.toBeChecked();
    fireEvent.click(screen.getByRole("checkbox", { name: /XP, levels/ }));
    expect(screen.getByRole("checkbox", { name: /Shop/ })).not.toBeChecked(); // the shop needs play
    await expectAccessible(container);
    fireEvent.click(screen.getByRole("button", { name: /Continue/ }));
    fireEvent.change(await screen.findByLabelText("Login"), { target: { value: "Admin" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "a-strong-password" } });
    await expectAccessible(container);
    fireEvent.click(screen.getByRole("button", { name: /Continue/ }));
    expect(await screen.findByRole("heading", { name: "Ready to create the portal" })).toBeInTheDocument();
    expect(calls.some((c) => c.method !== "GET")).toBe(false); // nothing written before the last step
    fireEvent.click(screen.getByRole("button", { name: /Create the portal/ }));
    await vi.waitFor(() => expect(assign).toHaveBeenCalledWith("/admin/setup"));
    const created = calls.find((c) => c.method === "POST" && c.path === "/api/v1/admin/first-run");
    expect(created?.body).toMatchObject({ login: "admin", settings: { "i18n.defaultLanguage": "en" } });
    expect(calls.some((c) => c.path === "/api/v1/auth/login")).toBe(true);
    const disabled = calls.filter((c) => c.path === "/api/v1/admin/modules" && c.method === "PUT");
    expect(disabled.map((c) => (c.body as { key: string }).key)).toEqual(["wiki"]);
    vi.unstubAllGlobals();
  });
});
