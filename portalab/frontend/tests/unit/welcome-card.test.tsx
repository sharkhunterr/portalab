import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 027 T083 — the first-visit welcome introduces header, sections and themes; dismissing it stores
// ``shell.welcome.dismissedAt`` on the account, so it never comes back (on any device).

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { WelcomeCard } from "../../src/features/dashboard/WelcomeCard";
import { json } from "../support/fake-api";

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([{ path: "/", element: <WelcomeCard /> }]);
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("welcome card", () => {
  it("shows once and stores the dismissal on the account", async () => {
    window.localStorage.clear();
    const puts: unknown[] = [];
    fake.handler = async (request) => {
      if (request.method === "PUT") puts.push(await request.json());
      return json(200, { preferences: [] });
    };
    show();
    expect(await screen.findByRole("heading", { name: "Welcome to your portal!" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Choose a theme" })).toHaveAttribute(
      "href",
      "/settings/appearance",
    );
    fireEvent.click(screen.getByRole("button", { name: "Got it" }));
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(Object.keys(puts[0] as object)).toEqual(["shell.welcome.dismissedAt"]);
    expect(screen.queryByRole("heading", { name: "Welcome to your portal!" })).toBeNull();
  });

  it("stays hidden once dismissed on another device", async () => {
    window.localStorage.clear();
    fake.handler = () =>
      json(200, { preferences: [{ key: "shell.welcome.dismissedAt", value: "2026-10-04T10:00:00Z" }] });
    const { container } = show();
    await waitFor(() => expect(container.querySelector(".welcome-card")).toBeNull());
  });
});
