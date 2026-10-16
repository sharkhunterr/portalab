import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// 017 T027 — every statistic state (locked, insufficient data, stale, partial, unavailable, no data) renders
// through FunctionalState with text and an icon under the light, dark and high-contrast themes.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { PreferencesProvider } from "../../src/design-system/a11y/PreferencesProvider";
import { ThemeProvider } from "../../src/design-system/themes/ThemeProvider";
import { StatCard } from "../../src/features/statistics/cards/StatCard";
import { json } from "../support/fake-api";
import { BUILTIN_THEMES } from "../support/themes";

globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
} as unknown as typeof ResizeObserver;

const STATES: Array<[string, string]> = [
  ["locked", "unauthorized"],
  ["insufficient_data", "no-data"],
  ["stale", "stale"],
  ["partial", "partial"],
  ["unavailable", "unavailable"],
  ["no_data", "no-data"],
];

const entry = (key: string) => ({
  key,
  title_key: key,
  description_key: null,
  domain: "d",
  scope: "community",
  viz: "line",
  hideable: true,
  locked: false,
  unlock_hint: null,
  period_options: ["day"],
  hidden: false,
});

describe("statistic states across themes", () => {
  it.each(["light", "dark", "high-contrast"])("%s", async (theme) => {
    fake.handler = (request) => {
      const state = decodeURIComponent(new URL(request.url).pathname.split("/").pop() ?? "");
      return json(200, {
        key: state,
        state,
        definition_version: 1,
        as_of: "2026-10-05T10:00:00Z",
        value: state === "stale" || state === "partial" ? 3 : null,
        series: [],
        breakdown: [],
        trend: null,
        unlock_hint: state === "locked" ? "statistics:unlock.campaign_active" : null,
        source_states: {},
        period_start: null,
        period_end: null,
      });
    };
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(
      <PreferencesProvider initial={{ theme }} policy={{ allowedThemes: ["light", "dark", "high-contrast"] }}>
        <ThemeProvider themes={BUILTIN_THEMES}>
          <QueryClientProvider client={client}>
            {STATES.map(([state]) => (
              <StatCard key={state} entry={entry(state)} query={{ period: "day" }} />
            ))}
          </QueryClientProvider>
        </ThemeProvider>
      </PreferencesProvider>,
    );
    for (const [state, functional] of STATES) {
      await waitFor(() => {
        const element = view.container.querySelector(
          `[data-statistic="${state}"] [data-state="${functional}"]`,
        );
        expect(element, state).toBeTruthy();
        expect(element?.textContent?.trim(), state).toBeTruthy();
        expect(element?.querySelector("svg[data-icon]"), state).toBeTruthy();
      });
    }
    view.unmount();
  });
});
