import { act, fireEvent, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";

// 004 T016/T024 — shell slots on every route; route change keeps the shell mounted (state preserved);
// landmarks and skip link; search and AI entries everywhere, AI outage degraded while search works.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { json } from "../../support/fake-api";
import { renderShell, VIEW } from "./harness";

describe("AppShell", () => {
  it("renders landmarks, slots and navigation, and stays mounted across routes", async () => {
    fake.handler = () => json(200, VIEW);
    const { container, router } = renderShell();
    expect(await screen.findByRole("link", { name: "Services" })).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main-content");
    expect(screen.getByRole("button", { name: /Search/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Assistant/ })).toHaveAttribute("aria-disabled", "true");
    const banner = screen.getByRole("banner");
    await act(() => router.navigate("/account"));
    expect(await screen.findByRole("heading", { name: "Account page" })).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBe(banner); // same element: the shell was not remounted
    // 027: personal pages live in the avatar menu; the section of the current page is marked instead
    expect(screen.getByRole("button", { name: /Personal menu/ })).toBeInTheDocument();
    // the section of the previous page folds away once another page is current
    expect(screen.getByRole("button", { name: "Portal" })).toHaveAttribute("aria-expanded", "false");
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });

  it("search works through the palette even without a search engine, AI available when provided", async () => {
    fake.handler = () => json(200, VIEW);
    const open = vi.fn();
    renderShell({ slots: { ai: { available: true, open } } });
    await screen.findByRole("link", { name: "Services" });
    fireEvent.click(screen.getByRole("button", { name: "Assistant" }));
    expect(open).toHaveBeenCalledWith({ route: "/" });
    fireEvent.click(screen.getByRole("button", { name: /Search/ }));
    expect(await screen.findByRole("combobox")).toBeInTheDocument();
  });

  it("degraded navigation is explained without hiding the rest of the shell", async () => {
    fake.handler = () => json(200, { ...VIEW, groups: [], degraded: true });
    renderShell();
    expect(await screen.findByText("Navigation is limited right now.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Search/ })).toBeInTheDocument();
    expect(within(screen.getByRole("main")).getByRole("heading", { name: "Home page" })).toBeInTheDocument();
  });
});
