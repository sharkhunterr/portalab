import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

// 007 T031 — events operations: dead letters, quarantine, replay with confirmation; accessible states.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));

vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { EventsAdmin } from "../../src/features/admin";
import { json } from "../support/fake-api";

function withClient(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={client}>
      <main>{children}</main>
    </QueryClientProvider>
  );
}

describe("events admin", () => {
  it("lists dead letters and quarantine, asks to confirm a replay", async () => {
    let replayCalls = 0;
    fake.handler = async (request) => {
      const url = new URL(request.url);
      if (url.pathname.endsWith("/deliveries")) {
        return json(200, {
          items: [
            { consumer: "rewards", event_id: "e1", status: "dead", attempts: 8, last_error: "ValueError" },
          ],
        });
      }
      if (url.pathname.endsWith("/quarantine")) {
        return json(200, {
          items: [{ id: "q1", event_type: "x.y", reason: "unknown_type", detail: "unknown" }],
        });
      }
      replayCalls += 1;
      return replayCalls === 1
        ? json(409, { code: "authz.confirmation_required", confirmation: "c-1" })
        : json(202, { processed: 4 });
    };
    const { container } = render(withClient(<EventsAdmin />));
    expect(await screen.findByText("rewards")).toBeInTheDocument();
    expect(await screen.findByText("unknown_type")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Projection"), { target: { value: "scores" } });
    fireEvent.click(screen.getByRole("button", { name: "Rebuild" }));
    fireEvent.click(await screen.findByRole("button", { name: "Confirm the rebuild" }));
    expect(await screen.findByText("Rebuilt from 4 events.")).toBeInTheDocument();
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });
});
