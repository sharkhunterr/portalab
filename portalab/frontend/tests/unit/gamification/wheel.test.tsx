import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// issue 225 — the daily wheel: the server draws, the page turns the wheel to the segment it was told and
// writes what it gave once it stopped; the amounts are Portalab's words on every slice.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import "../../../src/features/gamification/widget";
import { widgetComponent } from "../../../src/features/dashboard/widgets/registry";
import {
  landingAngle,
  restingAngle,
  toneOf,
  type WheelState,
} from "../../../src/features/gamification/wheel/WheelWidget";
import { json } from "../../support/fake-api";

const SEGMENTS: WheelState["segments"] = [
  { key: "coins_20", kind: "coins", amount: 20 },
  { key: "lose_10", kind: "coins", amount: -10 },
  { key: "xp_100", kind: "xp", amount: 100 },
  { key: "booster", kind: "product", amount: 0, product: "booster_discovery", label: "Discovery booster" },
];

const state = (today: WheelState["today"] = null): WheelState => ({
  enabled: true,
  day: "2026-10-22",
  next_at: new Date(Date.now() + 3 * 3600_000).toISOString(),
  spin_ms: 5200,
  coins: 40,
  segments: SEGMENTS,
  today,
});

function show(data: WheelState) {
  const Widget = widgetComponent("gamification.daily_wheel");
  expect(Widget).toBeDefined();
  const Component = Widget as NonNullable<typeof Widget>;
  const element = <Component payload={{ state: "available", data } as never} config={{}} />;
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={createMemoryRouter([{ path: "/", element }])} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.useRealTimers());

describe("daily wheel", () => {
  it("lands on the segment drawn, under the pointer at the top", () => {
    expect(restingAngle(0, 4)).toBe(315); // the first slice's middle (45°) brought to the top
    expect(restingAngle(2, 4)).toBe(135);
    const end = landingAngle(100, 2, 4, 0);
    expect(end % 360).toBe(135);
    expect(end).toBeGreaterThan(100 + 5 * 360); // whole turns first
    // never on an edge: a jitter stays inside the slice
    expect(Math.abs((landingAngle(0, 1, 4, 5) % 360) - restingAngle(1, 4))).toBeLessThan(45);
    expect(SEGMENTS.map(toneOf)).toEqual(["coins", "lose", "xp", "product"]);
  });

  it("writes every slice's amount and offers today's spin", () => {
    show(state());
    const labels = [...document.querySelectorAll(".wheel__label")].map((l) => l.textContent);
    expect(labels.slice(0, 3)).toEqual(["+20", "−10", "+100XP"]);
    expect(document.querySelector('.wheel__slice[data-tone="lose"]')).not.toBeNull();
    expect(document.querySelector(".wheel")?.getAttribute("data-phase")).toBe("idle");
    expect((document.querySelector(".wheel__hub") as HTMLButtonElement).disabled).toBe(false);
  });

  it("turns to what the server drew, then says it", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const spun = state({
      segment: "lose_10",
      index: 1,
      kind: "coins",
      amount: -10,
      delta: -10,
      product: null,
      given: false,
      spun_at: new Date().toISOString(),
    });
    fake.handler = (request) =>
      request.method === "POST" && request.url.endsWith("/api/v1/me/wheel/spin")
        ? json(200, spun)
        : json(404, {});
    show(state());
    await act(async () => {
      fireEvent.click(document.querySelector(".wheel__hub") as HTMLButtonElement);
    });
    await vi.waitFor(() =>
      expect(document.querySelector(".wheel")?.getAttribute("data-phase")).toBe("spinning"),
    );
    const turned = (document.querySelector(".wheel__spinner") as HTMLElement).style.transform;
    const degrees = Number(/rotate\(([-\d.]+)deg\)/.exec(turned)?.[1]);
    expect(Math.abs((degrees % 360) - restingAngle(1, 4))).toBeLessThan(45);
    expect(document.querySelector(".wheel__outcome")).toBeNull(); // not said while it turns
    await act(async () => {
      vi.advanceTimersByTime(5300);
    });
    expect(document.querySelector(".wheel")?.getAttribute("data-phase")).toBe("done");
    expect(document.querySelector('.wheel__outcome[data-tone="lose"]')).not.toBeNull();
  });

  it("rests on today's spin, the booster sent to the reserve", () => {
    show(
      state({
        segment: "booster",
        index: 3,
        kind: "product",
        amount: 0,
        delta: 0,
        product: "booster_discovery",
        given: true,
        spun_at: new Date().toISOString(),
      }),
    );
    expect(document.querySelector(".wheel")?.getAttribute("data-phase")).toBe("done");
    expect((document.querySelector(".wheel__hub") as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("link").getAttribute("href")).toBe("/marketplace/reserve");
    expect(document.querySelector(".wheel__outcome")?.textContent).toContain("Discovery booster");
  });
});
