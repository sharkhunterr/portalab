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
import { SystemVersion } from "../../src/features/admin/backup/SystemVersion";
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

  it("arrival wizard (issues 246, 249): language, installation, identity, features, administrator, then everything at once", async () => {
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
    // issue 249: the portal's name, before anything else
    fireEvent.change(await screen.findByLabelText("Portal name"), { target: { value: "Xenoportal" } });
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
    // the password typed twice: a different one keeps the step
    fireEvent.change(screen.getByLabelText("Confirm the password"), {
      target: { value: "a-strong-passwork" },
    });
    expect(screen.getByText("The two passwords are not the same.")).toBeInTheDocument();
    fireEvent.submit(container.querySelector("#arrival-admin") as HTMLFormElement);
    expect(screen.getByRole("alert")).toHaveTextContent("The two passwords are not the same.");
    fireEvent.change(screen.getByLabelText("Confirm the password"), {
      target: { value: "a-strong-password" },
    });
    expect(screen.getByText("The passwords match.")).toBeInTheDocument();
    await expectAccessible(container);
    fireEvent.click(screen.getByRole("button", { name: /Continue/ }));
    expect(await screen.findByRole("heading", { name: "Ready to create the portal" })).toBeInTheDocument();
    expect(screen.getByText("Xenoportal", { selector: "strong" })).toBeInTheDocument();
    expect(calls.some((c) => c.method !== "GET")).toBe(false); // nothing written before the last step
    fireEvent.click(screen.getByRole("button", { name: /Create the portal/ }));
    // the waiting screens: the ring, the tasks, until it is all in place
    expect(await screen.findByRole("progressbar", { name: "Setting up the portal" })).toBeInTheDocument();
    expect(await screen.findByText("All set!")).toBeInTheDocument();
    await expectAccessible(container);
    const created = calls.find((c) => c.method === "POST" && c.path === "/api/v1/admin/first-run");
    expect(created?.body).toMatchObject({
      login: "admin",
      settings: { "i18n.defaultLanguage": "en", "admin.setup.progress": { arrival: { step: "services" } } },
    });
    expect(calls.some((c) => c.path === "/api/v1/auth/login")).toBe(true);
    const site = calls.find((c) => c.method === "PUT" && c.path === "/api/v1/admin/site");
    expect(site?.body).toMatchObject({ name: "Xenoportal" });
    const disabled = calls.filter((c) => c.path === "/api/v1/admin/modules" && c.method === "PUT");
    expect(disabled.map((c) => (c.body as { key: string }).key)).toEqual(["wiki"]);
  }, 20_000); // many screens, each checked by axe
  it("arrival wizard signed in (issue 249): who may join, then the portal opens behind its waiting screens", async () => {
    const calls: Array<{ method: string; path: string; body: unknown }> = [];
    let progress: Record<string, unknown> = { done: ["account"], arrival: { step: "access" } };
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      const body = request.method === "GET" ? null : await request.json().catch(() => null);
      calls.push({ method: request.method, path, body });
      if (path === "/api/v1/auth/site") return json(200, { name: "Xenoportal" });
      if (path === "/api/v1/admin/config" && request.method === "PUT") {
        const change = (body as { changes: Array<{ key: string; value: unknown }> }).changes[0];
        if (change?.key === "admin.setup.progress") progress = change.value as Record<string, unknown>;
        return json(200, {});
      }
      if (path === "/api/v1/admin/config")
        return json(200, {
          settings: [
            { key: "admin.setup.progress", value: progress, source: "global" },
            { key: "identity.registrationMode", value: "invite_only", source: "default" },
          ],
        });
      if (path === "/api/v1/services") return json(200, { items: [] });
      if (path === "/api/v1/admin/modules") return json(200, []); // every feature kept
      if (path === "/api/v1/admin/ai/servers") return json(200, []);
      if (path === "/api/v1/admin/ai/config")
        return json(200, { values: { enabled: false }, provider_secret_set: false });
      return json(200, {});
    };
    const { ArrivalContinue } = await import("../../src/features/admin/arrival/ArrivalContinue");
    const { Routes, Route } = await import("react-router");
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const { container } = render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/setup"]}>
          <Routes>
            <Route path="/setup" element={<ArrivalContinue />} />
            <Route path="/" element={<p>the portal</p>} />
            <Route path="/admin/setup" element={<p>the setup assistant</p>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByRole("heading", { name: "Who may join the portal" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /By invitation/ })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: /Open sign-up/ }));
    await vi.waitFor(() =>
      expect(
        calls.some(
          (c) =>
            c.method === "PUT" &&
            JSON.stringify(c.body).includes('"identity.registrationMode","value":"open"'),
        ),
      ).toBe(true),
    );
    await expectAccessible(container);
    fireEvent.click(screen.getByRole("button", { name: /Skip/ })); // the e-mail: later
    fireEvent.click(await screen.findByRole("button", { name: /Skip/ }));
    // issue 249: the look, then play and the AI assistant (their features are kept), as in the setup assistant
    expect(await screen.findByRole("heading", { name: "The portal's look" })).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { pressed: false })[0] as HTMLElement);
    await vi.waitFor(() =>
      expect(
        calls.some((c) => c.method === "PUT" && JSON.stringify(c.body).includes("ui.defaultTheme")),
      ).toBe(true),
    );
    await expectAccessible(container);
    fireEvent.click(screen.getByRole("button", { name: /Skip/ }));
    expect(await screen.findByRole("heading", { name: "Play and the shop" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Skip/ }));
    expect(await screen.findByRole("heading", { name: "The AI assistant" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Skip/ }));
    expect(await screen.findByRole("heading", { name: "Everything is ready" })).toBeInTheDocument();
    expect(screen.getByText("no service yet")).toBeInTheDocument();
    await expectAccessible(container);
    fireEvent.click(screen.getByRole("button", { name: /Open my portal/ }));
    expect(await screen.findByText("Welcome to Xenoportal!")).toBeInTheDocument();
    expect(await screen.findByText("the portal", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(progress).toMatchObject({ arrival: { step: "open" }, step: "summary" });
    expect((progress.arrival as { finished_at?: string }).finished_at).toBeTruthy();
  }, 20_000); // many screens, each checked by axe
  it("version page (issue 247): what runs here, and the reset only once the portal's name is typed", async () => {
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/auth/site") return json(200, { name: "Xenoportal" });
      if (path === "/api/v1/admin/system/version")
        return json(200, {
          portalab: "0.1.0",
          archive_format: 2,
          python: "3.12.3",
          database: "PostgreSQL 16.14",
          started_at: "2026-10-25T09:00:00Z",
          schema: [{ module: "identity", revision: "identity_0007" }],
        });
      return json(200, {});
    };
    const { container } = render(withClient(<MemoryRouter>{<SystemVersion />}</MemoryRouter>));
    expect(await screen.findByText("0.1.0")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Show the module"));
    expect(screen.getByText("identity_0007")).toBeInTheDocument();
    const go = screen.getByRole("button", { name: /Erase everything/ });
    expect(go).toBeDisabled();
    fireEvent.change(await screen.findByLabelText(/Type the portal's name to confirm: Xenoportal/), {
      target: { value: "xenoportal" },
    });
    fireEvent.change(screen.getByLabelText("Your password"), { target: { value: "secret" } });
    expect(go).toBeEnabled();
    await expectAccessible(container);
  });
});
