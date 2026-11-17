import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Issue 479 — a statistic's change told plainly: the direction in words and the figures without their sign
// (never « down -26 »), « new » when nothing came before, and no comparison with a period it did not cover.

vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => () => new Response(null, { status: 404 }) });
  return importOriginal();
});

import type { StatResult } from "../../../src/features/statistics/api";
import { StatChart } from "../../../src/features/statistics/charts/StatChart";

const result = (trend: StatResult["trend"], value: number | null = 51) =>
  ({
    key: "trends.achievements_unlocked",
    state: "available",
    definition_version: 1,
    value,
    series: [],
    breakdown: [],
    trend,
    source_states: {},
  }) as unknown as StatResult;

const show = (stat: StatResult) =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <StatChart result={stat} viz="number" title="Achievements" />
    </QueryClientProvider>,
  );

describe("a statistic's trend (issue 479)", () => {
  it("says down without a double minus", () => {
    const { container } = show(result({ delta: -26, direction: "down", previous_value: 77, percent: -33.8 }));
    expect(screen.getByText(/^Down 26 \(34%\) versus the previous period$/)).toBeTruthy();
    // the badge, as My media tells it: an arrow, red, the share of change
    expect(container.querySelector('[data-trend="down"]')?.textContent).toContain("34% vs previous period");
  });

  it("says new when nothing came before", () => {
    show(result({ delta: 6, direction: "up", previous_value: 0, percent: null }, 6));
    expect(screen.getByText("New: nothing over the previous period")).toBeTruthy();
  });

  it("tells there is no comparison when the statistic did not cover the previous period", () => {
    const { container } = show(result(null, 26));
    expect(screen.getByText("No comparison")).toBeTruthy();
    expect(container.querySelector('[data-trend="none"]')?.getAttribute("title")).toBe(
      "No comparison: this statistic does not cover the previous period yet",
    );
  });
});
