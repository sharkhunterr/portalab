import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 010 T013/T016 — the bell's panel (issue 112: the only place) lists items with their kind as text, reads,
// archives (and brings back), deletes — one or several at once — and marks all as read; preferences show mandatory channels checked, explained and not editable, and save per channel.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { NotificationPanel } from "../../../src/features/notifications/bell/NotificationPanel";
import { NotificationPreferences } from "../../../src/features/notifications/preferences/NotificationPreferences";
import { json } from "../../support/fake-api";

const item = (id: string, extra: Record<string, unknown> = {}) => ({
  id,
  kind: "notification",
  category: "media.new",
  priority: "normal",
  title: `Item ${id}`,
  body: "",
  count: 1,
  action_url: null,
  read: false,
  archived: false,
  created_at: "2026-10-03T10:00:00Z",
  updated_at: "2026-10-03T10:00:00Z",
  ...extra,
});

function wrap(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("notification panel", () => {
  it("shows kind as text, and acts on each item: read, archive, delete", async () => {
    const calls: string[] = [];
    fake.handler = (request) => {
      const url = new URL(request.url);
      if (request.method !== "GET") {
        calls.push(`${request.method} ${url.pathname}`);
        return request.method === "DELETE" ? new Response(null, { status: 204 }) : json(200, { read: 1 });
      }
      return json(200, {
        items: [
          item("a", { kind: "alert", priority: "critical", title: "Service down", count: 3 }),
          item("b", { read: true }),
        ],
        next_cursor: null,
        unread: 1,
      });
    };
    wrap(<NotificationPanel open onOpenChange={() => {}} />);
    const alert = (await screen.findByText("Service down")).closest("li") as HTMLElement;
    expect(within(alert).getByText("Alert")).toBeTruthy();
    expect(within(alert).getByText("×3")).toBeTruthy();
    fireEvent.click(within(alert).getByRole("button", { name: "Mark as read: Service down" }));
    fireEvent.click(within(alert).getByRole("button", { name: "Archive: Service down" }));
    fireEvent.click(within(alert).getByRole("button", { name: "Delete: Service down" }));
    fireEvent.click(screen.getByRole("button", { name: "Mark all as read" }));
    await waitFor(() =>
      expect(calls).toEqual([
        "POST /api/v1/me/notifications/a/read",
        "POST /api/v1/me/notifications/a/archive",
        "DELETE /api/v1/me/notifications/a",
        "POST /api/v1/me/notifications/read-all",
      ]),
    );
    // issue 112: no other page to go to
    expect(screen.queryByText("See every notification")).toBeNull();
  });

  it("filters, shows the archive, and acts on several at once", async () => {
    const queries: string[] = [];
    const bulk: unknown[] = [];
    fake.handler = async (request) => {
      const url = new URL(request.url);
      if (request.method === "POST") {
        bulk.push(await request.json());
        return json(200, { done: 2 });
      }
      queries.push(url.search);
      const archived = url.searchParams.get("archived") === "true";
      return json(200, {
        items: archived
          ? [item("z", { archived: true, read: true, title: "Old one" })]
          : [item("a"), item("b")],
        next_cursor: null,
        unread: 2,
      });
    };
    wrap(<NotificationPanel open onOpenChange={() => {}} />);
    await screen.findByText("Item a");
    fireEvent.click(screen.getByRole("tab", { name: "Alerts" }));
    await waitFor(() => expect(queries.some((q) => q.includes("kind=alert"))).toBe(true));
    fireEvent.click(screen.getByRole("tab", { name: /^All/ }));
    await screen.findByText("Item a");
    // select: both, then archive them in one go; delete asks to be confirmed
    fireEvent.click(screen.getByRole("button", { name: "Select" }));
    fireEvent.click(screen.getByRole("button", { name: "Select all" }));
    expect(screen.getByText("2 selected")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Archive" }));
    await waitFor(() => expect(bulk).toEqual([{ ids: ["a", "b"], action: "archive" }]));
    fireEvent.click(screen.getByRole("checkbox", { name: "Select: Item a" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(bulk).toHaveLength(1); // not yet
    fireEvent.click(screen.getByRole("button", { name: "Delete 1 notification?" }));
    await waitFor(() => expect(bulk.at(-1)).toEqual({ ids: ["a"], action: "delete" }));
    // the archive: brought back from there
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    fireEvent.click(screen.getByRole("tab", { name: "Archived" }));
    const old = (await screen.findByText("Old one")).closest("li") as HTMLElement;
    fireEvent.click(within(old).getByRole("button", { name: "Unarchive: Old one" }));
    await waitFor(() => expect(bulk.at(-1)).toEqual({ ids: ["z"], action: "unarchive" }));
  });
});

describe("notification preferences", () => {
  it("explains mandatory channels and saves one channel at a time", async () => {
    const bodies: unknown[] = [];
    const prefs = {
      digest: "off",
      categories: [
        {
          key: "account.security",
          label_key: "notifications:category.security",
          user_mutable: false,
          channels: {
            portal: { enabled: true, mandatory: true, locked: true },
            email: { enabled: true, mandatory: false, locked: true },
          },
        },
        {
          key: "system.maintenance",
          label_key: "notifications:category.maintenance",
          user_mutable: true,
          channels: {
            portal: { enabled: true, mandatory: false, locked: false },
            email: { enabled: false, mandatory: false, locked: false },
          },
        },
      ],
    };
    fake.handler = async (request) => {
      if (request.method === "PUT") bodies.push(await request.json());
      return json(200, prefs);
    };
    wrap(<NotificationPreferences />);
    const security = await screen.findByRole("checkbox", { name: "Account security: In the portal" });
    expect((security as HTMLInputElement).checked).toBe(true);
    expect((security as HTMLInputElement).disabled).toBe(true);
    expect(screen.getByText("Required by your administrator.")).toBeTruthy();
    fireEvent.click(screen.getByRole("checkbox", { name: "Scheduled maintenance: By e-mail" }));
    await waitFor(() => expect(bodies).toEqual([{ preferences: { "system.maintenance": { email: true } } }]));
    expect(await screen.findByText("Preferences saved.")).toBeTruthy();
  });

  it("shows an outage once and sets both its categories (issue 124)", async () => {
    const bodies: unknown[] = [];
    const channel = (enabled: boolean) => ({ enabled, mandatory: false, locked: false });
    const prefs = {
      digest: "off",
      categories: [
        {
          key: "system.health",
          label_key: "notifications:category.health",
          user_mutable: true,
          channels: { portal: channel(true), email: channel(false) },
        },
        {
          key: "system.health_email",
          label_key: "notifications:category.healthEmail",
          user_mutable: true,
          channels: { portal: channel(true), email: channel(true) },
        },
      ],
    };
    fake.handler = async (request) => {
      if (request.method === "PUT") bodies.push(await request.json());
      return json(200, prefs);
    };
    wrap(<NotificationPreferences />);
    const email = await screen.findByRole("checkbox", { name: "Service outages: By e-mail" });
    expect((email as HTMLInputElement).checked).toBe(true); // what the e-mail companion does
    expect(screen.queryByText("Service outages (e-mail)")).toBeNull();
    fireEvent.click(screen.getByRole("checkbox", { name: "Service outages: In the portal" }));
    await waitFor(() =>
      expect(bodies).toEqual([
        { preferences: { "system.health": { portal: false }, "system.health_email": { portal: false } } },
      ]),
    );
  });
});
