import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 015 T021/T024 — the product page lists every condition by name, met or not, in text; acquisition stays
// disabled while one is unmet; the refund policy is stated before purchase.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { ProductDetail } from "../../../src/features/marketplace/product/ProductDetail";
import { json } from "../../support/fake-api";

function show(element: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider
        router={createMemoryRouter([{ path: "/p/:key", element }], { initialEntries: ["/p/night_owl"] })}
      />
    </QueryClientProvider>,
  );
}

describe("marketplace product", () => {
  it("names the unmet conditions and blocks acquisition", async () => {
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/me/permissions") {
        return json(200, { permissions: ["marketplace.read", "marketplace.purchase"], roles: ["user"] });
      }
      return json(200, {
        key: "night_owl",
        type: "badge",
        state: "available",
        version: 1,
        name: "Night owl",
        names: { en: "Night owl" },
        descriptions: {},
        price_coins: 50,
        conditions: [{ kind: "min_level", level: 3 }],
        refund_policy: { refundable: true, window_days: 7, percent: 100 },
        config_required: false,
        repeatable: false,
        owned: false,
        eligibility: [
          { name: "min_level", value: 3, met: false, reason: "unmet" },
          { name: "coins", value: 50, met: true, reason: "" },
        ],
      });
    };
    show(<ProductDetail />);
    expect(await screen.findByRole("heading", { level: 1, name: "Night owl" })).toBeTruthy();
    expect(screen.getByText("Level 3 or more — not met")).toBeTruthy();
    expect(screen.getByText("50 Coins available — met")).toBeTruthy();
    const acquire = await screen.findByRole("button", { name: "Acquire" });
    expect((acquire as HTMLButtonElement).disabled).toBe(true);
  });
});
