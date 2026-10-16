import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

// 028 (US6, R26): what a pack's widget is handed — each contract it declared, projected to the contract's
// fields only; « forbidden » (and never read) when the member may not read it; never a contract it did not
// declare, nor one the portal does not offer.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
  requests: [] as string[],
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", {
    get: () => (request: Request) => {
      fake.requests.push(new URL(request.url).pathname);
      return fake.handler(request);
    },
  });
  return importOriginal();
});

import { CONTRACTS, contractOf, project, useContracts } from "../../../src/features/dashboard/contracts";
import { json } from "../../support/fake-api";

const PROGRESSION = {
  user_id: "0190f0a0-0000-7000-8000-000000000001",
  level: 7,
  xp: 1240,
  level_floor: 1000,
  next_level_at: 1500,
  coins: 320,
  reserved_coins: 15,
  contribution: 42,
  achievements: 9,
  boost: null,
};

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("widget data contracts", () => {
  it("offers the same contracts as the server's catalog", () => {
    expect(Object.keys(CONTRACTS).sort()).toEqual(
      ["me.progression", "me.statistics", "me.watching", "media.recently_added"].sort(),
    );
  });

  it("keeps a contract's fields only", () => {
    const value = project(CONTRACTS["me.progression"] as never, [PROGRESSION]) as Record<string, unknown>;
    expect(value).toEqual({
      level: 7,
      xp: 1240,
      level_floor: 1000,
      next_level_at: 1500,
      coins: 320,
      contribution: 42,
    });
    expect(value).not.toHaveProperty("user_id");
    const watching = project(CONTRACTS["me.watching"] as never, [
      [{ object_id: "secret", title: "Dune", kind: "movie", percent: 140, resume_position_s: 9 }],
    ]);
    expect(watching).toEqual({ items: [{ title: "Dune", kind: "movie", percent: 100 }] });
    const added = project(CONTRACTS["media.recently_added"] as never, [
      { items: [{ id: "x", image_id: "y", title: "Arcane", kind: "series", year: 2024 }] },
    ]);
    expect(added).toEqual({ items: [{ title: "Arcane", kind: "series", year: 2024 }] });
    // an answer that does not fit the contract hands nothing but an error
    expect(project(CONTRACTS["me.progression"] as never, [{ level: "high" }])).toEqual({ state: "error" });
  });

  it("reads only what was declared and may be read", async () => {
    fake.requests.length = 0;
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/me/progression") return json(200, PROGRESSION);
      if (path === "/api/v1/me/streak")
        return json(200, { days: 4, multiplier: 1.2, enabled: true, freezes: 0 });
      return json(404, {});
    };
    const { result } = renderHook(
      () =>
        useContracts(
          ["me.progression", "me.statistics", "media.recently_added", "me.password"],
          ["media.recently_added"],
        ),
      { wrapper },
    );
    await waitFor(() =>
      expect((result.current["me.statistics"] as { streak_days?: number }).streak_days).toBe(4),
    );
    expect(result.current["me.progression"]).toMatchObject({ level: 7, coins: 320 });
    expect(result.current["me.statistics"]).toEqual({
      streak_days: 4,
      streak_multiplier: 1.2,
      achievements: 9,
    });
    // forbidden: never read; unknown: never handed
    expect(result.current["media.recently_added"]).toEqual({ state: "forbidden" });
    expect(result.current).not.toHaveProperty("me.password");
    expect(fake.requests).not.toContain("/api/v1/media/discovery/new");
    expect([...new Set(fake.requests)].sort()).toEqual(["/api/v1/me/progression", "/api/v1/me/streak"]);
  });

  it("says forbidden when the portal refuses it", async () => {
    fake.handler = () => json(403, { title: "Forbidden", code: "authz.denied" });
    const { result } = renderHook(() => useContracts(["me.watching"], []), { wrapper });
    await waitFor(() => expect(result.current["me.watching"]).toEqual({ state: "forbidden" }));
  });

  it("hands any widget's data — and « forbidden » when the dashboard refuses it", async () => {
    expect(contractOf("widget:media.recently_added")).toBeDefined();
    expect(contractOf("widget:pack.vigie-cap")).toBeUndefined(); // a pack's widget holds no data
    expect(contractOf("widget:../me")).toBeUndefined();
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/widgets/media.recently_added/data")
        return json(200, { state: "available", as_of: null, data: { items: [{ title: "Arcane" }] } });
      if (path === "/api/v1/widgets/health.host/data") return json(200, { state: "unauthorized" });
      return json(404, {});
    };
    const { result } = renderHook(
      () => useContracts(["widget:media.recently_added", "widget:health.host"], []),
      { wrapper },
    );
    await waitFor(() =>
      expect(result.current["widget:media.recently_added"]).toEqual({
        state: "available",
        as_of: null,
        data: { items: [{ title: "Arcane" }] },
      }),
    );
    expect(result.current["widget:health.host"]).toEqual({ state: "forbidden" });
  });
});
