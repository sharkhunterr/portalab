import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 027 — a product opens from the shop in a panel (issue 244: the showcase is the shop): name, type, rarity, description, price and a
// pre-rendering by type (a pack lists what it contains; a notification style shows a sample notification);
// scarcity is shown (copies left, sold out) and « Buy » sits in the footer next to « Close ».

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import ShopPage from "../../../src/features/marketplace/vitrine/VitrinePage";
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
  product("crown", "title", "Crown", { label: "Royal" }, { rarity: "legendary", supply: 2, remaining: 0 }),
];

function show(entry = "/marketplace") {
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
        router={createMemoryRouter([{ path: "/marketplace", element: <ShopPage /> }], {
          initialEntries: [entry],
        })}
      />
    </QueryClientProvider>,
  );
}

describe("shop product modal", () => {
  it("opens a pack with its contents and price", async () => {
    show();
    fireEvent.click(await screen.findByRole("button", { name: /^Packs/ })); // 027: the packs department
    fireEvent.click(await screen.findByRole("link", { name: /Star pack/ }));
    const dialog = await screen.findByRole("dialog", { name: "Star pack" });
    expect(within(dialog).getByText("Star pack description")).toBeTruthy();
    expect(within(dialog).getByText("Neon notifications")).toBeTruthy();
    expect(within(dialog).getByText("Gold frame")).toBeTruthy();
    expect(await within(dialog).findByRole("button", { name: "Buy · 120 Coins" })).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "Close" })).toBeTruthy();
    expect(within(dialog).queryByText(/full page/)).toBeNull();
  });

  it("previews a notification style with a sample notification", async () => {
    show();
    // 027: notification looks are in the « Notifications & effects » department
    fireEvent.click(await screen.findByRole("button", { name: /^Notifications & effects/ }));
    fireEvent.click(await screen.findByRole("link", { name: /Neon notifications/ }));
    const dialog = await screen.findByRole("dialog", { name: "Neon notifications" });
    const stage = dialog.querySelector(".product-art__notify");
    expect(stage?.getAttribute("data-style")).toBe("neon");
    expect(stage?.querySelector(".ds-notification__title")?.textContent).toBeTruthy(); // decorative sample
  });
});

describe("shop scarcity", () => {
  it("shows the copies left inside the card and refuses a sold-out product", async () => {
    show();
    fireEvent.click(await screen.findByRole("button", { name: /^Profile/ })); // 027: titles are on the profile
    const link = await screen.findByRole("link", { name: /Crown/ });
    const card = link.closest(".vitrine-tile") as HTMLElement;
    expect(card.querySelector(".product-art__stock")?.textContent).toBe("Sold out");
    expect(card.querySelector(".product-art__type")?.textContent).toBe("Title");
    fireEvent.click(link);
    const dialog = await screen.findByRole("dialog", { name: "Crown" });
    expect(await within(dialog).findByText("Sold out: no copy left")).toBeTruthy();
    expect(within(dialog).queryByRole("button", { name: /Buy/ })).toBeNull();
  });
});

describe("shop links from elsewhere", () => {
  it("lands an « in the shop » link on its kind of product, then lets the whole department show", async () => {
    show("/marketplace?type=title");
    expect(await screen.findByRole("heading", { name: /^Title/ })).toBeTruthy();
    expect(await screen.findByRole("link", { name: /Crown/ })).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Gold frame/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "All types" }));
    expect(await screen.findByRole("link", { name: /Gold frame/ })).toBeTruthy(); // the profile department
  });

  it("still opens a department from the classic shop's links", async () => {
    show("/marketplace?department=packs");
    expect(await screen.findByRole("link", { name: /Star pack/ })).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Crown/ })).toBeNull();
  });
});

describe("shop previews' motion", () => {
  it("holds the previews still while browsing, not in the product opened (issue 381)", async () => {
    window.localStorage.removeItem("portalab.marketplace.stillPreviews");
    show();
    const toggle = await screen.findByRole("switch", { name: "Animated previews" });
    expect((toggle as HTMLInputElement).checked).toBe(true);
    fireEvent.click(await screen.findByRole("button", { name: /^Notifications & effects/ }));
    const link = await screen.findByRole("link", { name: /Neon notifications/ });
    const art = () => link.closest(".vitrine-tile")?.querySelector(".lazy-art") as HTMLElement;
    expect(art().hasAttribute("data-motion-still")).toBe(false);

    fireEvent.click(toggle);
    expect((toggle as HTMLInputElement).checked).toBe(false);
    expect(art().hasAttribute("data-motion-still")).toBe(true);
    expect(window.localStorage.getItem("portalab.marketplace.stillPreviews")).toBe("1");

    fireEvent.click(link);
    const dialog = await screen.findByRole("dialog", { name: "Neon notifications" });
    const stage = dialog.querySelector(".product-art__notify") as HTMLElement;
    expect(stage.closest("[data-motion-still]")).toBeNull(); // the product opened still moves
    window.localStorage.removeItem("portalab.marketplace.stillPreviews");
  });
});
