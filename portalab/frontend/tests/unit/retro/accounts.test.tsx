import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// Issue 426 — « My game library account »: the member authorises Portalab on their own RomM account (a code
// approved in RomM, the page asking until it is), then removes the authorisation; no card when retro play is
// switched off.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { RetroAccounts } from "../../../src/features/retro/RetroAccounts";
import { json } from "../../support/fake-api";

const SERVICE = "00000000-0000-0000-0000-000000000001";
const base = { service_id: SERVICE, service_name: "RomM", interval: 2 };

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RetroAccounts />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.useRealTimers());

describe("my game library account", () => {
  it("authorises Portalab with a code approved in RomM, then removes it", async () => {
    let approved = false;
    const calls: string[] = [];
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      calls.push(`${request.method} ${path}`);
      if (path === "/api/v1/retro/accounts" && request.method === "GET")
        return json(200, [{ ...base, state: "none" }]);
      if (path === `/api/v1/retro/accounts/${SERVICE}` && request.method === "POST")
        return json(200, {
          ...base,
          state: "pending",
          user_code: "ABCD-1234",
          approve_url: "https://romm.example/pair/device?user_code=ABCD-1234",
        });
      if (path === `/api/v1/retro/accounts/${SERVICE}/check`)
        return json(
          200,
          approved
            ? { ...base, state: "linked", username: "zoe" }
            : { ...base, state: "pending", user_code: "ABCD-1234" },
        );
      if (request.method === "DELETE") return json(204, null);
      return json(404, {});
    };
    vi.useFakeTimers({ shouldAdvanceTime: true });
    show();
    fireEvent.click(await screen.findByRole("button", { name: /Authorise Portalab/ }));
    expect(await screen.findByText("ABCD-1234")).toBeTruthy();
    const approve = screen.getByRole("link", { name: /Approve in RomM/ });
    expect(approve.getAttribute("href")).toBe("https://romm.example/pair/device?user_code=ABCD-1234");
    expect(approve.getAttribute("rel")).toContain("noopener");
    approved = true;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100);
    });
    expect(await screen.findByText("Your games go to your account « zoe »")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Remove the authorisation" }));
    await waitFor(() => expect(calls).toContain(`DELETE /api/v1/retro/accounts/${SERVICE}`));
  });

  it("shows nothing when retro play is switched off", async () => {
    fake.handler = () => json(503, { code: "retro.disabled", title: "Off" });
    show();
    await waitFor(() => expect(document.querySelector(".retro-account")).toBeNull());
    expect(screen.queryByText("My game library account")).toBeNull();
  });
});
