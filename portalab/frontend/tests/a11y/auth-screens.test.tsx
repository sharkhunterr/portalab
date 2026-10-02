import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import axe from "axe-core";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

// 002 T049 — the sign-in, activation and account screens have no axe violations, every field has a label
// and every control is reachable by keyboard.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));

vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { AccountPage, LoginForm, VerifyForm } from "../../src/features/auth";
import { json, ME } from "../support/fake-api";

function withClient(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <main>{children}</main>
    </QueryClientProvider>
  );
}

async function expectAccessible(container: HTMLElement) {
  const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  expect(results.violations.map((violation) => violation.id)).toEqual([]);
  for (const control of container.querySelectorAll("input, select, textarea, button")) {
    expect((control as HTMLElement).tabIndex).toBeGreaterThanOrEqual(0);
  }
}

describe("auth screens accessibility", () => {
  it("sign-in form", async () => {
    const { container } = render(withClient(<LoginForm />));
    await expectAccessible(container);
  });

  it("activation form", async () => {
    const { container } = render(withClient(<VerifyForm initialToken="abc" />));
    await expectAccessible(container);
  });

  it("account page", async () => {
    fake.handler = () => json(200, { ...ME, has_avatar: true });
    const { container } = render(withClient(<AccountPage />));
    expect(await screen.findByRole("heading", { name: "My account" })).toBeInTheDocument();
    await expectAccessible(container);
    expect(screen.getByLabelText("Who can see “About me”")).toHaveValue("private");
  });

  it("account page when signed out shows the unauthorized state", async () => {
    fake.handler = () => json(401, { code: "unauthorized" });
    const { container } = render(withClient(<AccountPage />));
    expect(await screen.findByText("Not allowed")).toBeInTheDocument();
    await expectAccessible(container);
  });
});
