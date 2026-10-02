import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

// 003 T035 — roles/groups/grants admin screens: loading/error/unauthorized states, keyboard operable
// controls, no axe violations, reserved refusal explained.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));

vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { AuthzAdminPage } from "../../src/features/authz";
import { json } from "../support/fake-api";

const ROLES = [
  { id: "01900000-0000-7000-8000-000000000004", key: "editor", name: "Editor", kind: "base", system: true },
];
const PERMISSIONS = [
  {
    key: "news.publish",
    description: "Publish",
    declared_by: "core",
    sensitive: true,
    reserved: false,
    requires_confirmation: false,
    user_grantable: false,
    enabled: true,
  },
  {
    key: "users.admin.transfer",
    description: "Transfer",
    declared_by: "core",
    sensitive: true,
    reserved: true,
    requires_confirmation: true,
    user_grantable: false,
    enabled: true,
  },
];

function api(request: Request): Response {
  const url = new URL(request.url);
  if (url.pathname === "/api/v1/roles") return json(200, ROLES);
  if (url.pathname === "/api/v1/groups") return json(200, []);
  if (url.pathname === "/api/v1/permissions") return json(200, PERMISSIONS);
  if (url.pathname.endsWith("/grants") && request.method === "GET") return json(200, []);
  if (url.pathname.endsWith("/grants")) return json(422, { code: "authz.reserved_permission" });
  return json(404, {});
}

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

describe("authz admin page", () => {
  it("is accessible and explains reserved refusals", async () => {
    fake.handler = api;
    const { container } = render(withClient(<AuthzAdminPage />));
    fireEvent.click(await screen.findByRole("button", { name: "Manage Editor" }));
    expect(await screen.findByText("No permission granted yet.")).toBeInTheDocument();
    const select = await screen.findByLabelText("Permission");
    expect(screen.getByRole("option", { name: /users.admin.transfer — Admin only/ })).toBeInTheDocument();
    fireEvent.change(select, { target: { value: "users.admin.transfer" } });
    fireEvent.click(screen.getByRole("button", { name: "Add the permission" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("reserved to the Admin");
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });

  it("shows the unauthorized state to non-admins", async () => {
    fake.handler = () => json(403, { code: "forbidden" });
    render(withClient(<AuthzAdminPage />));
    expect((await screen.findAllByText("Not allowed")).length).toBeGreaterThan(0);
  });
});
