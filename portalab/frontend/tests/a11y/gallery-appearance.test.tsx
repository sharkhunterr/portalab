import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

// 022 T039/T033 — the component gallery is axe-clean in every built-in theme; the appearance settings
// change presentation only, explain policy locks and keep the user's choice.

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
import { AppearanceSettings } from "../../src/features/appearance";
import { Gallery } from "../../src/features/dev/gallery/Gallery";
import { json } from "../support/fake-api";

const AXE = { rules: { "color-contrast": { enabled: false }, region: { enabled: false } } };

describe("gallery", () => {
  it.each(["light", "dark", "high-contrast"])("is axe-clean under %s", async (theme) => {
    const { container } = render(<Gallery />);
    fireEvent.change(screen.getByLabelText("Gallery theme"), { target: { value: theme } });
    expect(document.documentElement.dataset.theme).toBe(theme);
    expect(screen.getAllByRole("status").length).toBeGreaterThan(5);
    const results = await axe.run(container, AXE);
    expect(results.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
  });
});

function withClient(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("appearance settings", () => {
  it("updates presentation and explains locked settings", async () => {
    fake.handler = async () =>
      json(200, {
        preferences: [
          {
            key: "ui.density",
            locked: true,
            user_value: "spacious",
            user_value_retained: true,
            value: "comfortable",
          },
        ],
      });
    const { container } = render(
      withClient(
        <PreferencesProvider>
          <ThemeProvider>
            <main>
              <AppearanceSettings />
            </main>
          </ThemeProvider>
        </PreferencesProvider>,
      ),
    );
    fireEvent.change(screen.getByLabelText("Theme"), { target: { value: "dark" } });
    expect(document.documentElement.dataset.theme).toBe("dark");
    fireEvent.click(screen.getByLabelText("High contrast"));
    expect(document.documentElement.dataset.theme).toBe("high-contrast");
    fireEvent.change(screen.getByLabelText("Text size"), { target: { value: "1.5" } });
    expect(document.documentElement.style.getPropertyValue("--text-scale")).toBe("1.5");
    const density = await screen.findByText(/Set by your administrator/);
    expect(within(density.parentElement as HTMLElement).getByLabelText("Density")).toBeDisabled();
    expect(screen.getByText(/Your choice \(spacious\) is kept/)).toBeInTheDocument();
    const results = await axe.run(container, AXE);
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
});
