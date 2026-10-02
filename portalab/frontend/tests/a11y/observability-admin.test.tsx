import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

// 025 T033 — observability admin: ranked problems with diagnostics, two-axis labels (not color only),
// errors ack/resolve, anomalies validate/dismiss, a failing region (trends) does not break the others.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));

vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { ObservabilityAdmin } from "../../src/features/admin";
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

describe("observability admin", () => {
  it("shows ranked problems, two-axis health and lets the admin act", async () => {
    const posted: string[] = [];
    fake.handler = async (request) => {
      const url = new URL(request.url);
      if (request.method === "POST") {
        posted.push(url.pathname);
        return json(200, {});
      }
      if (url.pathname.endsWith("/overview")) {
        return json(200, {
          portal: { status: "degraded" },
          problems: [
            {
              kind: "component",
              id: "sync:s1",
              title: "Media sync: degraded",
              action_needed: true,
              since: "2026-10-01T12:00:00+00:00",
              diagnostics: [
                {
                  key: "rerun_sync",
                  label: "Synchronize now",
                  method: "POST",
                  path: "/api/v1/services/s1/sync",
                  permission: "services.manage",
                },
              ],
            },
          ],
          components: [{ component: "sync:s1", technical: "ok", functional: "failing", status: "degraded" }],
        });
      }
      if (url.pathname.endsWith("/errors")) {
        return json(200, {
          items: [
            {
              id: "e1",
              component: "jobs",
              category: "job_failed",
              message: "boom",
              count: 3,
              state: "open",
              last_seen_at: "x",
            },
          ],
        });
      }
      if (url.pathname.endsWith("/anomalies")) {
        return json(200, {
          items: [
            {
              id: "a1",
              detector: "long_sync",
              component: "sync:s1",
              severity: "warning",
              status: "pending_validation",
            },
          ],
        });
      }
      return json(503, { code: "observability.unavailable", title: "Unavailable" });
    };
    const { container } = render(withClient(<ObservabilityAdmin />));
    expect(await screen.findByText(/Media sync: degraded/)).toBeInTheDocument();
    expect(screen.getByText("Action needed:")).toBeInTheDocument();
    expect(screen.getByText("POST /api/v1/services/s1/sync")).toBeInTheDocument();
    expect(screen.getByText("Failing")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Acknowledge" }));
    fireEvent.change(screen.getByLabelText("Resolution note"), { target: { value: "fixed" } });
    fireEvent.click(screen.getByRole("button", { name: "Resolve" }));
    fireEvent.click(await screen.findByRole("button", { name: "Validate (incident)" }));
    await vi.waitFor(() => expect(posted).toHaveLength(3));
    expect(posted).toEqual([
      "/api/v1/admin/observability/errors/e1/ack",
      "/api/v1/admin/observability/errors/e1/resolve",
      "/api/v1/admin/observability/anomalies/a1/validate",
    ]);
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });
});
