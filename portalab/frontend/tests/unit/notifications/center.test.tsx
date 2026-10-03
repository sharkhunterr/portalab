import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 010 T013/T016 — the center lists items with kind/priority as text, reads/archives/deletes and marks all
// as read; preferences show mandatory channels checked, explained and not editable, and save per channel.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { NotificationCenter } from "../../../src/features/notifications/center/NotificationCenter";
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

describe("notification center", () => {
  it("shows kind and priority as text, and acts on items", async () => {
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
    wrap(<NotificationCenter />);
    const alert = (await screen.findByText("Service down")).closest("li") as HTMLElement;
    expect(within(alert).getByText("Alert")).toBeTruthy();
    expect(within(alert).getByText("Critical")).toBeTruthy();
    expect(within(alert).getByText("×3")).toBeTruthy();
    expect(screen.getByText("1 unread notification")).toBeTruthy();
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
  });

  it("filters alerts and unread items", async () => {
    const queries: string[] = [];
    fake.handler = (request) => {
      queries.push(new URL(request.url).search);
      return json(200, { items: [], next_cursor: null, unread: 0 });
    };
    wrap(<NotificationCenter />);
    expect(await screen.findByText("You have no notifications.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Alerts" }));
    await waitFor(() => expect(queries.some((q) => q.includes("kind=alert"))).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: "Unread" }));
    await waitFor(() => expect(queries.some((q) => q.includes("unread=true"))).toBe(true));
    expect(screen.getByRole("button", { name: "Unread" }).getAttribute("aria-pressed")).toBe("true");
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
});
