import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 027 T096 — theme studio: every theme with its source, accessibility and offer state; "Duplicate" opens the
// editor with a live preview and the accessibility floor; an unreadable color blocks saving; saving posts
// the definition and offers the new theme to members; axe clean.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));

vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import ThemeStudio from "../../src/features/appearance/studio/ThemeStudio";
import { json } from "../support/fake-api";
import { BUILTIN_THEMES } from "../support/themes";

function withClient(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <main>{children}</main>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("theme studio", () => {
  it("duplicates a theme, previews it, checks the floor and saves it", async () => {
    const calls: Array<{ method: string; path: string; body: unknown }> = [];
    fake.handler = async (request) => {
      const url = new URL(request.url);
      const body = request.method === "GET" ? null : await request.json();
      calls.push({ method: request.method, path: url.pathname, body });
      if (url.pathname === "/api/v1/admin/ui/themes" && request.method === "GET") {
        return json(200, {
          items: BUILTIN_THEMES.map((theme) => ({
            key: theme.key,
            name: theme.name,
            definition: theme,
            source: "builtin",
            enabled: true,
            floor_ok: true,
          })),
        });
      }
      if (url.pathname === "/api/v1/ui/themes") {
        return json(200, { themes: [], policy: { allowedThemes: ["portalab-dark", "orbit"] } });
      }
      if (url.pathname === "/api/v1/admin/marketplace/products") {
        return json(200, [{ key: "theme_orbit", type: "theme", state: "available", theme: "orbit" }]);
      }
      if (url.pathname === "/api/v1/admin/ui/themes" && request.method === "POST") return json(201, {});
      return json(200, { applied: true });
    };
    const { container } = render(withClient(<ThemeStudio />));
    const list = await screen.findByRole("list", { name: "Themes" });
    const orbit = (await within(list).findByText("Orbit")).closest("li") as HTMLElement;
    expect(within(orbit).getByText("In the shop")).toBeInTheDocument();
    expect(within(orbit).queryByRole("button", { name: "Stop offering" })).toBeNull(); // sold, not "offered"

    fireEvent.click(screen.getByRole("button", { name: "New theme" }));
    const name = await screen.findByLabelText("Name");
    expect((name as HTMLInputElement).value).toMatch(/copy/);
    fireEvent.change(name, { target: { value: "Night Shift" } });
    expect((screen.getByLabelText("Technical key") as HTMLInputElement).value).toBe("night-shift");
    expect(screen.getByRole("complementary", { name: "Live preview" })).toBeInTheDocument();
    expect(screen.getByText(/passes the accessibility floor/)).toBeInTheDocument();

    const text = screen.getByRole("textbox", { name: "Text" });
    const original = (text as HTMLInputElement).value;
    const background = (screen.getByRole("textbox", { name: "Background" }) as HTMLInputElement).value;
    fireEvent.change(text, { target: { value: background } }); // unreadable: text = background
    expect(await screen.findByText(/too low/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save the theme" })).toBeDisabled();
    fireEvent.change(text, { target: { value: original } });

    fireEvent.click(screen.getByRole("button", { name: "Save the theme" }));
    await vi.waitFor(() =>
      expect(calls.some((c) => c.method === "POST" && c.path === "/api/v1/admin/ui/themes")).toBe(true),
    );
    const saved = calls.find((c) => c.method === "POST" && c.path === "/api/v1/admin/ui/themes");
    expect(saved?.body).toMatchObject({ definition: { key: "night-shift", name: "Night Shift" } });
    expect(
      (saved?.body as { definition?: { family?: string } } | undefined)?.definition?.family,
    ).toBeUndefined();
    await vi.waitFor(() =>
      expect(
        calls.some(
          (c) =>
            c.method === "PUT" &&
            c.path === "/api/v1/admin/config" &&
            JSON.stringify(c.body).includes("night-shift"),
        ),
      ).toBe(true),
    ); // offered to members right away

    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  }, 20_000); // axe on the whole studio
});
