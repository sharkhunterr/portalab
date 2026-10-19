import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Issue 159 — the site's identity: the administrators' page previews the name, slogan and currency (the
// singular or the plural by the number) before saving, and saves them; the sign-in page and the tab carry
// the site's name, logo and slogan; the currency's icon replaces the coins.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
  requests: [] as Request[],
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  installed.requests = fake.requests;
  return importOriginal();
});

import { Icon } from "../../src/design-system/components/Icon";
import { SiteIdentityAdmin } from "../../src/features/admin/site/SiteIdentityAdmin";
import { AuthGate } from "../../src/features/auth/AuthGate";
import { SiteRoot } from "../../src/shell/site/site";
import { json } from "../support/fake-api";

const XENO = {
  name: "Xenoportal",
  short_name: "XP",
  custom: true,
  tagline: { fr: "Vos services, au même endroit." },
  currency: { en: { one: "Xenocoin", other: "Xenocoins" } },
  currency_short: "XC",
  currency_icon: "gem",
  logo: "/api/v1/auth/site/logo?v=3",
  icon: "/api/v1/auth/site/icon?v=3",
  version: 3,
};
const EMPTY_ADMIN = {
  name: null,
  short_name: null,
  default_name: "Portalab",
  custom: false,
  tagline: {},
  currency: {},
  currency_short: null,
  currency_icon: null,
  logo: null,
  icon: null,
  version: 0,
};

function show(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

beforeEach(() => {
  fake.requests.length = 0;
});

describe("the site's identity", () => {
  it("previews the name and the currency, then saves them", async () => {
    let saved: unknown = null;
    fake.handler = async (request) => {
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/admin/site" && request.method === "PUT") {
        saved = await request.json();
        return json(200, { ...EMPTY_ADMIN, ...(saved as object), custom: true, version: 1 });
      }
      if (url.pathname === "/api/v1/admin/site") return json(200, EMPTY_ADMIN);
      if (url.pathname === "/api/v1/i18n/languages")
        return json(200, { default: "en", items: [{ code: "en", name_native: "English" }] });
      return json(200, {});
    };
    show(<SiteIdentityAdmin />);
    const name = await screen.findByLabelText("Site name");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save" }).hasAttribute("disabled")).toBe(false),
    );
    fireEvent.change(name, { target: { value: "Xenoportal" } });
    fireEvent.change(screen.getByLabelText("Short name", { selector: "input[maxlength='12']" }), {
      target: { value: "XP" },
    });
    fireEvent.change(screen.getByLabelText("Singular"), { target: { value: "Xenocoin" } });
    fireEvent.change(screen.getByLabelText("Plural"), { target: { value: "Xenocoins" } });
    fireEvent.change(screen.getByLabelText("Short name", { selector: "input[maxlength='8']" }), {
      target: { value: "XC" },
    });
    expect(screen.getAllByText("Xenoportal").length).toBeGreaterThan(0); // the header and the card
    expect(screen.getByText("Spend 1 Xenocoin?")).toBeTruthy();
    expect(screen.getByText("Spend 120 Xenocoins?")).toBeTruthy();
    expect(document.querySelector(".site-preview .ds-currency-short")?.textContent).toBe("\u00a0XC");

    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(saved).not.toBeNull());
    expect(saved).toMatchObject({
      name: "Xenoportal",
      short_name: "XP",
      currency: { en: { one: "Xenocoin", other: "Xenocoins" } },
      currency_short: "XC",
      currency_icon: null,
    });
    expect(await screen.findByRole("status")).toBeTruthy();
  });

  it("names the sign-in page, the tab and the currency's icon", async () => {
    fake.handler = (request) => {
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/auth/site") return json(200, XENO);
      if (url.pathname === "/api/v1/me") return new Response(null, { status: 401 });
      return json(200, {});
    };
    show(
      <SiteRoot>
        <AuthGate location={{ pathname: "/", search: "" }}>{() => <p>portal</p>}</AuthGate>
        <Icon name="coins" />
      </SiteRoot>,
    );
    expect(await screen.findByText("Xenoportal")).toBeTruthy();
    expect(screen.getByText("Vos services, au même endroit.")).toBeTruthy(); // the only slogan written
    await waitFor(() => expect(document.title).toBe("Xenoportal"));
    expect(document.head.querySelector<HTMLLinkElement>('link[rel="icon"]')?.href).toContain(
      "/auth/site/icon",
    );
    expect(document.querySelector("img.ds-auth__logo")?.getAttribute("src")).toBe(XENO.logo);
    expect(document.querySelector('[data-icon="gem"]')).toBeTruthy(); // in place of the coins
  });
});
