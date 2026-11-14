import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// Spec 032 — « Who's there? », the PIN pad, « My household » and its profile editor have no axe violation,
// every field has a label and every control is reachable by keyboard.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import HouseholdPage from "../../src/features/household/HouseholdPage";
import { ProfileGate } from "../../src/features/household/ProfilePicker";
import { json } from "../support/fake-api";

const OWNER = "0190f0a0-0000-7000-8000-000000000001";
const LEA = "0190f0a0-0000-7000-8000-000000000002";
const tile = (id: string, name: string, kind: string, extra: Record<string, unknown> = {}) => ({
  id,
  display_name: name,
  kind,
  color: "#6366f1",
  has_avatar: false,
  has_pin: false,
  needs_pin: false,
  ...extra,
});
const figures = { xp: 400, level: 3, coins: 40, contribution: 2 };

function withClient(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

async function expectAccessible(container: HTMLElement) {
  const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  expect(results.violations.map((violation) => violation.id)).toEqual([]);
  for (const control of container.querySelectorAll("input, select, textarea, button")) {
    // the inactive tabs (one tab stop, arrows inside) and a dialog's hidden default button are not stops
    if (control.closest("[hidden], [aria-hidden='true'], [role='tablist']")) continue;
    expect((control as HTMLElement).tabIndex).toBeGreaterThanOrEqual(0);
  }
}

describe("household accessibility", () => {
  it("the picker and its PIN pad", async () => {
    fake.handler = () =>
      json(200, {
        enabled: true,
        owner_id: OWNER,
        active_id: OWNER,
        must_choose: true,
        members: [
          tile(OWNER, "Alice", "owner"),
          tile(LEA, "Léa", "child", { has_pin: true, needs_pin: true }),
        ],
      });
    const { container } = render(withClient(<ProfileGate>portal</ProfileGate>));
    await screen.findByRole("heading", { name: "Who's there?" });
    await expectAccessible(container);
    fireEvent.click(screen.getByRole("button", { name: /Léa/ }));
    await expectAccessible((await screen.findByRole("dialog")) as HTMLElement);
  });

  it("my household and the profile editor", async () => {
    fake.handler = (request) =>
      new URL(request.url).pathname === "/api/v1/household/requests"
        ? json(200, [])
        : json(200, {
            enabled: true,
            owner_id: OWNER,
            me: OWNER,
            can_manage: true,
            max_profiles: 8,
            palette: ["#6366f1", "#ec4899"],
            totals: figures,
            members: [
              { ...tile(OWNER, "Alice", "owner"), progress: figures, community_visible: true },
              {
                ...tile(LEA, "Léa", "child"),
                progress: figures,
                community_visible: false,
                restrictions: { max_age: 12, allow_unrated: false, blocked: ["shop"] },
              },
            ],
          });
    const { container } = render(withClient(<HouseholdPage />));
    await screen.findByRole("heading", { name: "Household wallet" });
    await expectAccessible(container);
    fireEvent.click(screen.getByRole("button", { name: "Add a profile" }));
    await expectAccessible((await screen.findByRole("dialog")) as HTMLElement);
  });
});
