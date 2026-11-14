import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Spec 032 — households: « Who's there? » after signing in (the master first, then its profiles), the PIN
// pad for a protected profile (a wrong PIN said, the field emptied), the whole portal reloading as the
// chosen profile; « My household » (the shared wallet, every member's figures, the master's tools and the
// access requests it answers); a title above a profile's age rating, locked, with « Ask for access ».

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { chooseProfile } from "../../../src/features/household/api";
import HouseholdPage from "../../../src/features/household/HouseholdPage";
import { LockedTitle } from "../../../src/features/household/LockedTitle";
import { ProfileGate } from "../../../src/features/household/ProfilePicker";
import { ApiError } from "../../../src/state/regions";
import { json } from "../../support/fake-api";

const OWNER = "0190f0a0-0000-7000-8000-000000000001";
const LEA = "0190f0a0-0000-7000-8000-000000000002";
const TOM = "0190f0a0-0000-7000-8000-000000000003";
const tile = (id: string, name: string, kind: string, extra: Record<string, unknown> = {}) => ({
  id,
  display_name: name,
  kind,
  color: "#6366f1",
  has_avatar: false,
  has_pin: false,
  needs_pin: false,
  ...extra,
});
const SESSION = {
  enabled: true,
  owner_id: OWNER,
  active_id: TOM,
  must_choose: true,
  members: [
    tile(OWNER, "Alice", "owner"),
    tile(LEA, "Léa", "child", { has_pin: true, needs_pin: true }),
    tile(TOM, "Tom", "standard"),
  ],
};
const figures = (coins: number) => ({ xp: coins * 10, level: 3, coins, contribution: 2 });
const HOUSEHOLD = {
  enabled: true,
  owner_id: OWNER,
  me: OWNER,
  can_manage: true,
  max_profiles: 8,
  palette: ["#6366f1", "#ec4899"],
  totals: figures(120),
  members: [
    { ...tile(OWNER, "Alice", "owner"), progress: figures(120), community_visible: true },
    {
      ...tile(LEA, "Léa", "child", { has_pin: true }),
      progress: figures(15),
      community_visible: false,
      effective_age: 12,
      restrictions: { max_age: 12, allow_unrated: false, blocked: ["shop"], mode: "hide", requests: true },
    },
  ],
};
const REQUEST = {
  id: "0190f0a0-0000-7000-8000-0000000000aa",
  profile_id: LEA,
  profile_name: "Léa",
  kind: "media",
  subject_ref: "0190f0a0-0000-7000-8000-0000000000bb",
  title: "Alien",
  rating: "16",
  note: null,
  status: "pending",
  created_at: "2026-11-14T10:00:00Z",
  decided_at: null,
  expires_at: null,
};

const assign = vi.fn();
beforeEach(() => {
  assign.mockReset();
  vi.stubGlobal("location", { assign, search: "", href: "http://portal.test/" });
});
afterEach(() => vi.unstubAllGlobals());

function show(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("who's there", () => {
  it("asks who is there, then reloads the portal as the chosen profile", async () => {
    const sent: unknown[] = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/household/session") return json(200, SESSION);
      if (path === "/api/v1/household/switch") {
        sent.push(await request.json());
        return json(200, { active_id: OWNER });
      }
      return json(404, {});
    };
    show(
      <ProfileGate>
        <p>The portal</p>
      </ProfileGate>,
    );
    expect(await screen.findByRole("heading", { name: "Who's there?" })).toBeTruthy();
    expect(screen.queryByText("The portal")).toBeNull();
    const names = Array.from(document.querySelectorAll(".household-tile__name")).map((n) => n.textContent);
    expect(names).toEqual(["Alice", "Léa", "Tom"]); // the master first, then its profiles in order
    fireEvent.click(screen.getByRole("button", { name: /Alice/ }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("/"));
    expect(sent).toEqual([{ user_id: OWNER }]);
  });

  it("asks a protected profile's PIN and says a wrong one", async () => {
    let tries = 0;
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/household/session") return json(200, SESSION);
      if (path === "/api/v1/household/switch") {
        tries += 1;
        const body = (await request.json()) as { pin?: string };
        return body.pin === "1234"
          ? json(200, { active_id: LEA })
          : json(403, { code: "household.wrong_pin", title: "Wrong PIN" });
      }
      return json(404, {});
    };
    show(
      <ProfileGate>
        <p>The portal</p>
      </ProfileGate>,
    );
    fireEvent.click(await screen.findByRole("button", { name: /Léa/ }));
    const pad = await screen.findByRole("dialog", { name: "Léa's PIN" });
    for (const digit of "0000") fireEvent.click(within(pad).getByRole("button", { name: `Digit ${digit}` }));
    fireEvent.click(within(pad).getAllByRole("button", { name: "Open" })[0] as HTMLElement);
    expect(await within(pad).findByText("Wrong PIN, try again.")).toBeTruthy();
    const field = within(pad).getByLabelText("PIN") as HTMLInputElement;
    await waitFor(() => expect(field.value).toBe(""));
    fireEvent.change(field, { target: { value: "12a34" } });
    expect(field.value).toBe("1234");
    fireEvent.submit(field.closest("form") as HTMLFormElement);
    await waitFor(() => expect(assign).toHaveBeenCalledWith("/"));
    expect(tries).toBe(2);
  });

  it("opens a protected member's PIN pad straight from the avatar menu", async () => {
    fake.handler = () => json(200, { ...SESSION, must_choose: false });
    show(
      <ProfileGate>
        <p>The portal</p>
      </ProfileGate>,
    );
    expect(await screen.findByText("The portal")).toBeTruthy();
    act(() => chooseProfile(LEA));
    expect(await screen.findByRole("dialog", { name: "Léa's PIN" })).toBeTruthy();
  });

  it("shows the portal at once without profiles", async () => {
    fake.handler = () =>
      json(200, { ...SESSION, must_choose: false, members: [tile(OWNER, "Alice", "owner")] });
    show(
      <ProfileGate>
        <p>The portal</p>
      </ProfileGate>,
    );
    expect(await screen.findByText("The portal")).toBeTruthy();
  });
});

describe("my household", () => {
  it("shows the wallet, every member and the master's tools; the master answers a request", async () => {
    const decisions: unknown[] = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/household") return json(200, HOUSEHOLD);
      if (path === "/api/v1/household/requests") return json(200, [REQUEST]);
      if (path.endsWith("/decision")) {
        decisions.push(await request.json());
        return json(204, null);
      }
      return json(404, {});
    };
    show(<HouseholdPage />);
    expect(await screen.findByRole("heading", { name: "My household" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Household wallet" })).toBeTruthy();
    expect(screen.getAllByText("120").length).toBeGreaterThan(0);
    expect(screen.getByText("Up to 12+")).toBeTruthy();
    expect(screen.getByText("Hidden from the community")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Edit Léa" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add a profile" })).toBeTruthy();

    fireEvent.mouseDown(screen.getByRole("tab", { name: "Requests (1)" }));
    fireEvent.click(screen.getByRole("tab", { name: "Requests (1)" }));
    expect(await screen.findByText("Léa asks for “Alien”")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Allow for 1 day" }));
    await waitFor(() => expect(decisions).toEqual([{ approve: true, days: 1 }]));
  });

  it("opens the editor with the profile's restrictions", async () => {
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/household") return json(200, HOUSEHOLD);
      if (path === "/api/v1/household/requests") return json(200, []);
      return json(404, {});
    };
    show(<HouseholdPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Edit Léa" }));
    const editor = await screen.findByRole("dialog", { name: "Edit Léa" });
    expect((within(editor).getByLabelText("Maximum age rating") as HTMLSelectElement).value).toBe("12");
    expect((within(editor).getByLabelText("Shop") as HTMLInputElement).checked).toBe(true);
    expect((within(editor).getByLabelText("AI assistant") as HTMLInputElement).checked).toBe(false);
    expect((within(editor).getByRole("radio", { name: /Child/ }) as HTMLInputElement).checked).toBe(true);
    // 032: a birth date sets the age (the fixed one is then disabled), hidden or locked titles, requests
    fireEvent.change(within(editor).getByLabelText("Birth date (optional)"), {
      target: { value: "2016-03-10" },
    });
    expect((within(editor).getByLabelText("Maximum age rating") as HTMLSelectElement).disabled).toBe(true);
    expect(within(editor).getByText(/years old today/)).toBeTruthy();
    fireEvent.click(within(editor).getByRole("radio", { name: /Shown locked/ }));
    expect((within(editor).getByRole("radio", { name: /Shown locked/ }) as HTMLInputElement).checked).toBe(
      true,
    );
    expect((within(editor).getByLabelText("May ask for access") as HTMLInputElement).checked).toBe(true);
  });

  it("hides the master's tools from a profile", async () => {
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/household") return json(200, { ...HOUSEHOLD, me: LEA, can_manage: false });
      if (path === "/api/v1/household/requests") return json(200, []);
      return json(404, {});
    };
    show(<HouseholdPage />);
    expect(await screen.findByRole("heading", { name: "Household wallet" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Edit Léa" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Add a profile" })).toBeNull();
    expect(screen.getByRole("button", { name: "My PIN" })).toBeTruthy();
  });
});

describe("a locked title", () => {
  it("says when the profile cannot ask", () => {
    const problem = new ApiError(403, "restricted", "household.restricted", {
      object_id: REQUEST.subject_ref,
      name: "Alien",
      rating: "16",
      can_ask: false,
    });
    show(<LockedTitle problem={problem} />);
    expect(screen.getByText("Your profile cannot ask for access to this title.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Ask for access" })).toBeNull();
  });

  it("asks the master for access", async () => {
    const sent: unknown[] = [];
    fake.handler = async (request) => {
      sent.push(await request.json());
      return json(200, { id: REQUEST.id, status: "pending", created: true });
    };
    const problem = new ApiError(403, "restricted", "household.restricted", {
      object_id: REQUEST.subject_ref,
      name: "Alien",
      rating: "16",
    });
    show(<LockedTitle problem={problem} />);
    expect(screen.getByRole("heading", { name: "Locked for your profile" })).toBeTruthy();
    expect(screen.getByText("Rated 16")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("A word for the master (optional)"), {
      target: { value: "please" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask for access" }));
    expect(await screen.findByText(/Request sent/)).toBeTruthy();
    expect(sent).toEqual([
      { kind: "media", ref: REQUEST.subject_ref, title: "Alien", rating: "16", note: "please" },
    ]);
  });
});
