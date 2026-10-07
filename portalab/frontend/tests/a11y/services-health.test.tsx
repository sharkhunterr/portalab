import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 006 T024 — services overview and detail: text-labelled states, independent sections (one unavailable
// while the others render), tier-shaped sections from the server, keyboard-operable, axe-clean.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));

vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { ServicesHealth } from "../../src/features/services";
import { json } from "../support/fake-api";

function withClient(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <main>{children}</main>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const AT = "2026-10-01T12:00:00+00:00";

describe("services health", () => {
  it("shows states with labels and independent detail sections", async () => {
    fake.handler = async (request) => {
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/incidents") return json(200, []);
      if (url.pathname === "/api/v1/maintenance") return json(200, { items: [] });
      if (url.pathname === "/api/v1/services/health") {
        return json(200, {
          items: [
            { id: "s1", name: "Media", connector: "fake", state: "degraded", availability: 0.995 },
            { id: "s2", name: "Books", connector: "fake", state: "maintenance", availability: null },
          ],
        });
      }
      return json(200, {
        service: { id: "s1", name: "Media" },
        sections: {
          state: { state: "available", as_of: AT, data: { state: "degraded", since: AT } },
          availability: { state: "unavailable", as_of: AT, detail: "This section did not load in time." },
          maintenance: {
            state: "available",
            as_of: AT,
            data: [{ id: "m1", title: "Disk upgrade", starts_at: AT, ends_at: AT }],
          },
          incidents: { state: "no-data", as_of: AT, data: null },
          sync: { state: "available", as_of: AT, data: { status: "idle", last_success_at: AT } },
          infrastructure: {
            state: "available",
            as_of: AT,
            data: {
              metrics: { cpu: { available: true, value: 12.5, unit: "%" }, gpu: { available: false } },
            },
          },
        },
      });
    };
    const { container } = render(withClient(<ServicesHealth />));
    expect(await screen.findByText("Degraded")).toBeInTheDocument();
    expect(screen.getByText("1 service is in trouble")).toBeInTheDocument(); // 027: the overall status
    expect(screen.queryByRole("link", { name: /add/i })).toBeNull(); // members do not add services
    expect(screen.getByText("Under maintenance")).toBeInTheDocument();
    expect(screen.getByText(/99.5% available/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Details of Media" }));
    const detail = await screen.findByRole("article", { name: "Media — health" });
    expect(await within(detail).findByText("This section did not load in time.")).toBeInTheDocument();
    expect(within(detail).getByText(/Disk upgrade/)).toBeInTheDocument();
    expect(within(detail).getByText("No data yet")).toBeInTheDocument();
    expect(within(detail).getByText("not available")).toBeInTheDocument(); // never zero
    expect(within(detail).getByText(/idle · last success/)).toBeInTheDocument();
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });
});
