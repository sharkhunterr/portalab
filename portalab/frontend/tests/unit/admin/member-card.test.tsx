import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// The member card (/admin/members/:userId): the member's name and state in the header, one tab per part of
// their picture driven by ?tab=, and each tab asks its list for this member only.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import MemberCard from "../../../src/features/admin/members/MemberCard";
import { json } from "../../support/fake-api";

const ADA = {
  id: "u1",
  login: "ada",
  display_name: "Ada",
  state: "suspended",
  created_at: "2026-01-01T00:00:00Z",
  last_sign_in_at: null,
  email: "ada@example.org",
};

function show(path: string, sent: unknown[] = []) {
  const asked: string[] = [];
  fake.handler = async (request) => {
    const url = new URL(request.url);
    asked.push(`${url.pathname}${url.search}`);
    if (url.pathname === "/api/v1/users/u1/password") {
      sent.push(await request.json());
      return json(200, { sessions_signed_out: 2 });
    }
    if (url.pathname === "/api/v1/users") return json(200, { items: [ADA], next_cursor: null });
    if (url.pathname === "/api/v1/support/tickets") return json(200, { items: [], next_cursor: null });
    if (url.pathname.endsWith("/roles") || url.pathname === "/api/v1/roles") return json(200, []);
    return json(200, []);
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider
        router={createMemoryRouter([{ path: "/admin/members/:userId", element: <MemberCard /> }], {
          initialEntries: [path],
        })}
      />
    </QueryClientProvider>,
  );
  return asked;
}

describe("member card", () => {
  it("shows the member and their state, and opens a tab", async () => {
    show("/admin/members/u1");
    expect(await screen.findByRole("heading", { name: "Ada" })).toBeTruthy();
    expect(screen.getAllByText("@ada · ada@example.org").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /Profile & roles|memberCard.tabs.profile/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Vigilance|memberCard.tabs.vigilance/ }));
    expect(await screen.findByRole("button", { name: /Reactivate/ })).toBeTruthy();
  });

  it("asks the support lists for this member only", async () => {
    const asked = show("/admin/members/u1?tab=support");
    await screen.findByRole("heading", { name: "Ada" });
    await vi.waitFor(() => {
      expect(asked).toContain("/api/v1/support/tickets?requester=u1");
      expect(asked).toContain("/api/v1/support/feedback?user_id=u1");
    });
  });

  it("sets the member's password, confirmed with the administrator's own (issue 348)", async () => {
    const sent: unknown[] = [];
    show("/admin/members/u1", sent);
    await screen.findByRole("heading", { name: "Ada" });
    const fill = (label: RegExp, value: string) =>
      fireEvent.change(screen.getByLabelText(label), { target: { value } });
    fill(/^New password|signInPhrase.new/, "a brand new passphrase");
    fill(/^Confirm the new password|signInPhrase.again/, "a brand new passphrase");
    fill(/Your own password|password.yours/, "mine");
    fireEvent.click(screen.getByRole("button", { name: /Set the password|password.submit/ }));
    expect(await screen.findByText(/2 sessions of the member|password.done/)).toBeTruthy();
    expect(sent).toEqual([{ password: "mine", new_password: "a brand new passphrase" }]);
  });

  it("says when the member does not exist", async () => {
    show("/admin/members/nobody");
    expect(await screen.findByText(/notFound|does not exist/)).toBeTruthy();
  });
});
