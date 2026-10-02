import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

// 021 T036/T038 — privacy center, overrides admin and audit viewer: accessible, explicit states.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));

vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { AuditViewer, PoliciesAdmin, PrivacyCenter } from "../../src/features/privacy";
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

async function expectAccessible(container: HTMLElement) {
  const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  expect(results.violations.map((violation) => violation.id)).toEqual([]);
}

describe("privacy screens", () => {
  it("privacy center shows the inventory and admin locks", async () => {
    fake.handler = () =>
      json(200, {
        data: [
          {
            datum_class: "profile_field",
            owner: "module:identity",
            classification: "personal",
            description: "Optional profile fields",
            default_level: "private",
            effective_level: "private",
            locked_by_policy: true,
            user_choosable: true,
            retention_days: null,
          },
        ],
        export_endpoint: "/api/v1/me/export",
        deletion_endpoint: "/api/v1/me/deletion",
      });
    const { container } = render(withClient(<PrivacyCenter />));
    expect(await screen.findByRole("rowheader", { name: "Optional profile fields" })).toBeInTheDocument();
    expect(screen.getByText(/your own choice is kept/)).toBeInTheDocument();
    await expectAccessible(container);
  });

  it("overrides admin explains stacking refusals", async () => {
    fake.handler = (request) =>
      request.method === "GET" ? json(200, []) : json(409, { code: "privacy.policy_exists" });
    const { container } = render(withClient(<PoliciesAdmin />));
    expect(await screen.findByText("No active override.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "moderation" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already active");
    await expectAccessible(container);
  });

  it("audit viewer shows redacted context", async () => {
    fake.handler = () =>
      json(200, {
        items: [
          {
            seq: 3,
            occurred_at: "2026-10-01T12:00:00Z",
            action: "user.suspended",
            actor_kind: "user",
            decision: "allow",
            result: "success",
            resource_type: "user",
            context: { redacted: true, keys: ["reason"] },
          },
        ],
        next_cursor: null,
      });
    const { container } = render(withClient(<AuditViewer />));
    expect(await screen.findByText(/Details hidden \(reason\)/)).toBeInTheDocument();
    await expectAccessible(container);
  });

  it("audit viewer shows the unauthorized state", async () => {
    fake.handler = () => json(403, { code: "forbidden" });
    render(withClient(<AuditViewer />));
    expect(await screen.findByText("Not allowed")).toBeInTheDocument();
  });
});
