import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 014 — the banner lists my active campaigns; the theme overlay uses the allowed theme the server chose;
// console actions need a reason and a confirmation; simulation explains each modifier in text.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { ActiveCampaignBanner } from "../../../src/features/campaigns/banner/ActiveCampaignBanner";
import CampaignConsole from "../../../src/features/campaigns/console/CampaignConsole";
import { useCampaignOverlay } from "../../../src/features/campaigns/presentation/CampaignPresentationProvider";
import { json } from "../../support/fake-api";

function wrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

function show(element: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter([{ path: "/", element }])} />
    </QueryClientProvider>,
  );
}

const CAMPAIGN = {
  id: "c1",
  key: "halloween",
  state: "active",
  current_version: 1,
  timezone: "Europe/Paris",
  definition: {
    names: { en: "Halloween", fr: "Halloween" },
    timezone: "Europe/Paris",
    schedule: {
      start_at: "2026-10-20T00:00:00",
      end_at: "2026-11-01T00:00:00",
      recurrence: { kind: "yearly" },
    },
    modifiers: [
      { id: "horror_xp", value: "xp", factor: 2, when: { media_kind: ["movie"], genre: ["horror"] } },
    ],
    discounts: [{ id: "spooky", percent: 20, products: ["pumpkin"], categories: [] }],
  },
  created_at: "2026-10-01T12:00:00Z",
};

describe("campaigns", () => {
  it("shows my active campaigns", async () => {
    fake.handler = () =>
      json(200, [{ key: "halloween", name: "Halloween", ends_at: "2026-10-31T23:00:00Z" }]);
    show(<ActiveCampaignBanner />);
    const link = await screen.findByRole("link", { name: "Halloween" });
    expect(link.getAttribute("href")).toBe("/campaigns/halloween");
    expect(screen.getByRole("complementary", { name: "Campaign" })).toBeTruthy();
  });

  it("builds the overlay from the allowed theme", async () => {
    fake.handler = () => json(200, { campaigns: [], theme: { campaign: "halloween", theme_key: "pumpkin" } });
    const themes = [
      { key: "pumpkin", colors: { accent: "#ff7518" } },
      { key: "light", colors: {} },
    ];
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useCampaignOverlay(themes), { wrapper: wrapper(client) });
    await waitFor(() => expect(result.current).toEqual({ key: "halloween", colors: { accent: "#ff7518" } }));
    const none = renderHook(() => useCampaignOverlay([]), { wrapper: wrapper(client) });
    expect(none.result.current).toBeNull();
  });

  it("confirms actions and explains simulations", async () => {
    const posts: Array<{ path: string; body: Record<string, unknown> }> = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (request.method === "GET") return json(200, [CAMPAIGN]);
      const body = (await request.json()) as Record<string, unknown>;
      posts.push({ path, body });
      if (path.endsWith("/simulate"))
        return json(200, [
          {
            modifier: "horror_xp",
            value: "xp",
            factor: 2,
            version: 1,
            verdict: "match",
            source_ref: "campaign:halloween:1:horror_xp",
          },
          {
            modifier: "title_xp",
            value: "xp",
            factor: 2,
            version: 1,
            verdict: "unknown",
            source_ref: "campaign:halloween:1:title_xp",
          },
        ]);
      return body.confirmation
        ? json(200, { ...CAMPAIGN, state: "paused" })
        : json(409, {
            code: "authz.confirmation_required",
            title: "Confirmation required",
            confirmation: "tok",
          });
    };
    show(<CampaignConsole />);
    const deactivate = await screen.findByRole("button", { name: "Deactivate" });
    expect((deactivate as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Server load" } });
    fireEvent.click(deactivate);
    expect(await screen.findByText("Confirm this change?")).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: "Deactivate" })[1] as HTMLElement);
    await waitFor(() =>
      expect(posts.at(-1)?.body).toMatchObject({ reason: "Server load", confirmation: "tok" }),
    );
    const summary = screen.getByText("Simulate", { selector: "summary" });
    (summary.parentElement as HTMLDetailsElement).open = true;
    fireEvent(summary.parentElement as HTMLElement, new Event("toggle"));
    fireEvent.click(await screen.findByRole("button", { name: "Simulate" }));
    expect(await screen.findByText(/horror_xp · xp ×2 — applies/)).toBeTruthy();
    expect(screen.getByText(/unknown attributes \(not applied\)/)).toBeTruthy();
  });
});
