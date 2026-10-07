import { QueryClient } from "@tanstack/react-query";
import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// 027 T022/T046 — the personal header shows avatar, level + XP, Coins, notifications, search and the
// personal menu; each element fails on its own (no progression ⇒ no chip, nothing else hidden); live
// progression changes patch the cache; the frame picks the arrangement the theme chose per device class.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { builtinTheme } from "../../src/design-system/themes/builtin";
import { presentationOf } from "../../src/design-system/themes/schema";
import { applyChange, PROGRESSION_KEY } from "../../src/shell/header/useHeaderData";
import { arrangementFor } from "../../src/shell/nav/NavFrame";
import { json, ME } from "../support/fake-api";
import { renderShell, setViewport, VIEW } from "./shell/harness";

const PROGRESSION = {
  user_id: ME.id,
  xp: 240,
  level: 3,
  level_floor: 200,
  next_level_at: 400,
  contribution: 0,
  coins: 12450,
  reserved_coins: 0,
  achievements: 2,
};

function backend(overrides: Record<string, () => Response> = {}) {
  return (request: Request) => {
    const path = new URL(request.url).pathname;
    if (overrides[path]) return (overrides[path] as () => Response)();
    if (path === "/api/v1/me") return json(200, ME);
    if (path === "/api/v1/me/progression") return json(200, PROGRESSION);
    if (path === "/api/v1/me/notifications/unread-count") return json(200, { unread: 3 });
    if (path === "/api/v1/me/navigation") return json(200, VIEW);
    return json(200, {});
  };
}

describe("personal header", () => {
  it("shows identity, level with progress, Coins and the unread count", async () => {
    setViewport(1280);
    fake.handler = backend();
    renderShell();
    const banner = screen.getByRole("banner");
    expect(await within(banner).findByRole("img", { name: "Level 3" })).toBeInTheDocument();
    expect(within(banner).getByRole("progressbar", { name: "Level 3: 40 of 200 XP" })).toHaveAttribute(
      "aria-valuenow",
      "20",
    );
    expect(within(banner).getByRole("img", { name: "Coins: 12,450" })).toHaveTextContent("12.5K");
    expect(
      await within(banner).findByRole("button", { name: /Notifications: 3 unread/ }),
    ).toBeInTheDocument();
    expect(within(banner).getByRole("button", { name: "Personal menu: Alice" })).toBeInTheDocument();
    expect(within(banner).getByRole("combobox", { name: /Search/ })).toBeInTheDocument();
  });

  it("keeps everything else when progression is unavailable", async () => {
    setViewport(1280);
    fake.handler = backend({ "/api/v1/me/progression": () => json(503, { title: "down" }) });
    renderShell();
    const banner = screen.getByRole("banner");
    expect(await within(banner).findByRole("button", { name: "Personal menu: Alice" })).toBeInTheDocument();
    expect(within(banner).queryByRole("img", { name: /Level/ })).toBeNull();
    expect(within(banner).getByRole("combobox", { name: /Search/ })).toBeInTheDocument();
  });

  it("patches the cached progression from a live change", () => {
    const client = new QueryClient();
    client.setQueryData(PROGRESSION_KEY, PROGRESSION);
    applyChange(client, {
      xp: 410,
      level: 4,
      level_floor: 400,
      next_level_at: 700,
      coins: 12500,
      delta_xp: 170,
      delta_coins: 0,
      level_up: true,
    });
    expect(client.getQueryData(PROGRESSION_KEY)).toMatchObject({ level: 4, xp: 410, coins: 12500 });
  });
});

describe("frame arrangement", () => {
  const portalab = presentationOf(builtinTheme("portalab-dark") as never);

  it("follows the theme per device class", () => {
    expect(arrangementFor("desktop", portalab).nav).toBe("sidebar");
    expect(arrangementFor("tablet", portalab).nav).toBe("rail");
    expect(arrangementFor("phone", portalab).nav).toBe("drawer"); // 027: no bottom bar by default
  });

  it("merges a footer header with the phone bottom bar", () => {
    const footer = { ...portalab, headerPosition: "bottom" as const };
    expect(arrangementFor("phone", footer)).toMatchObject({ nav: "drawer", headerPosition: "bottom" });
    const orbit = { ...portalab, nav: { ...portalab.nav, desktop: "orbit" as const } };
    expect(arrangementFor("desktop", orbit).nav).toBe("orbit");
  });

  it("keeps the essentials in the phone header and the page when the class changes", async () => {
    setViewport(390);
    fake.handler = backend();
    renderShell();
    // 027: no bottom bar — home and search on the left, notifications and the menu on the right
    expect(await screen.findByRole("link", { name: "Home" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open navigation" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Sections" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Home page" })).toBeInTheDocument();
    setViewport(1280);
  });
});
