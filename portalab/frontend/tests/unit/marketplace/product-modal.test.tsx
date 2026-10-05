import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 027 — a product opens from the shop in a modal: name, type, rarity, description, price and a preview by
// type (a pack lists what it contains; a notification style shows a sample notification).

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import CatalogPage from "../../../src/features/marketplace/catalog/CatalogPage";
import { json } from "../../support/fake-api";

function product(key: string, type: string, name: string, preview: Record<string, unknown>, extra = {}) {
  return {
    key,
    type,
    state: "available",
    version: 1,
    name,
    names: { en: name },
    descriptions: { en: `${name} description` },
    price_coins: 120,
    conditions: [],
    refund_policy: { refundable: false },
    config_required: false,
    repeatable: false,
    owned: false,
    rarity: "epic",
    preview,
    eligibility: [],
    ...extra,
  };
}

const PRODUCTS = [
  product("notif_neon", "notification_style", "Neon notifications", { style: "neon" }),
  product("frame_gold", "avatar_frame", "Gold frame", { frame: "gold" }, { owned: true }),
  product("pack_star", "bundle", "Star pack", { products: ["notif_neon", "frame_gold"] }),
];

function show() {
  fake.handler = (request) => {
    const path = new URL(request.url).pathname;
    if (path === "/api/v1/me/permissions") {
      return json(200, { permissions: ["marketplace.read", "marketplace.purchase"], roles: ["user"] });
    }
    if (path === "/api/v1/marketplace/products") return json(200, PRODUCTS);
    if (path.startsWith("/api/v1/marketplace/products/")) {
      return json(
        200,
        PRODUCTS.find((p) => path.endsWith(`/${p.key}`)),
      );
    }
    if (path === "/api/v1/marketplace/categories") return json(200, []);
    if (path === "/api/v1/me") return json(200, { id: "u1", display_name: "Ada", has_avatar: false });
    return json(404, {});
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider
        router={createMemoryRouter([{ path: "/marketplace", element: <CatalogPage /> }], {
          initialEntries: ["/marketplace"],
        })}
      />
    </QueryClientProvider>,
  );
}

describe("shop product modal", () => {
  it("opens a pack with its contents and price", async () => {
    show();
    fireEvent.click(await screen.findByRole("link", { name: "Star pack" }));
    const dialog = await screen.findByRole("dialog", { name: "Star pack" });
    expect(within(dialog).getByText("Star pack description")).toBeTruthy();
    expect(within(dialog).getByText("Neon notifications")).toBeTruthy();
    expect(within(dialog).getByText("Gold frame")).toBeTruthy();
    expect(await within(dialog).findByRole("button", { name: /Acquire/ })).toBeTruthy();
  });

  it("previews a notification style with a sample notification", async () => {
    show();
    fireEvent.click(await screen.findByRole("link", { name: "Neon notifications" }));
    const dialog = await screen.findByRole("dialog", { name: "Neon notifications" });
    const stage = dialog.querySelector(".product-preview__stage");
    expect(stage?.getAttribute("data-style")).toBe("neon");
    expect(within(dialog).getAllByRole("status").length).toBeGreaterThan(0);
  });
});
