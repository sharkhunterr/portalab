import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
import { KeptNotice, LockedTitle } from "../../../src/features/household/LockedTitle";
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
  it("shows the family's dashboard: the wallet, each member's watching, the requests waiting", async () => {
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/household") return json(200, HOUSEHOLD);
      if (path === "/api/v1/household/requests") return json(200, [REQUEST]);
      if (path === "/api/v1/me/media/household")
        return json(200, {
          days: 7,
          members: [
            {
              user_id: OWNER,
              minutes: 0,
              plays: 0,
              finished: 0,
              kinds: {},
              series: [0, 0, 0, 0, 0, 0, 0],
              streak: 0,
            },
            {
              user_id: LEA,
              minutes: 95,
              plays: 4,
              finished: 1,
              kinds: { movie: 60, book: 35 },
              series: [0, 0, 10, 20, 0, 30, 35],
              streak: 2,
              last: {
                title: "Coco",
                kind: "movie",
                object_id: REQUEST.subject_ref,
                at: "2026-11-14T18:00:00Z",
              },
              screen: { used: 35, allowed: 60, open: true, slots: [] },
            },
          ],
        });
      return json(404, {});
    };
    show(<HouseholdPage />);
    expect(await screen.findByRole("heading", { name: "Family dashboard" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Household wallet" })).toBeTruthy();
    expect(await screen.findByText(/1 access request waits/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Answer" }).getAttribute("href")).toBe("/household/requests");
    const lea = (await screen.findByRole("heading", { name: "Léa" })).closest("li") as HTMLElement;
    expect(within(lea).getByRole("link", { name: "Coco" })).toBeTruthy();
    expect(within(lea).getByText("Screen time today: 35 / 60 min")).toBeTruthy();
    expect(within(lea).getAllByText(/2 days in a row/).length).toBeGreaterThan(0);
    expect(screen.getByText(/2 days · Léa/)).toBeTruthy(); // the longest streak
    fireEvent.click(screen.getByRole("button", { name: "30 days" }));
    expect(screen.getByRole("button", { name: "30 days" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("lists the profiles and the master's tools; the master answers a request", async () => {
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
    show(<HouseholdPage view="profiles" />);
    expect(await screen.findByText("Up to 12+")).toBeTruthy();
    expect(screen.getByText("Hidden from the community")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Edit Léa" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add a profile" })).toBeTruthy();
    cleanup();
    show(<HouseholdPage view="requests" />);
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
    show(<HouseholdPage view="profiles" />);
    fireEvent.click(await screen.findByRole("button", { name: "Edit Léa" }));
    const editor = await screen.findByRole("dialog", { name: "Edit Léa" });
    expect((within(editor).getByLabelText("Maximum age rating") as HTMLSelectElement).value).toBe("12");
    // 032: switches — a feature or a kind of content on is allowed, a genre on is kept out
    expect((within(editor).getByLabelText("Shop") as HTMLInputElement).checked).toBe(false);
    expect((within(editor).getByLabelText("AI assistant") as HTMLInputElement).checked).toBe(true);
    expect((within(editor).getByLabelText("Books") as HTMLInputElement).checked).toBe(true);
    expect((within(editor).getByLabelText("Horror") as HTMLInputElement).checked).toBe(false);
    fireEvent.click(within(editor).getByLabelText("Horror"));
    expect((within(editor).getByLabelText("Horror") as HTMLInputElement).checked).toBe(true);
    expect(within(editor).getByLabelText("Most screen time on Monday")).toBeTruthy(); // issue 432: the planner
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

  it("gives time in a few taps: minutes more today, no limits for a while, the limits back", async () => {
    const posted: Array<[string, unknown]> = [];
    let household: unknown = {
      ...HOUSEHOLD,
      members: HOUSEHOLD.members.map((m) =>
        m.id === LEA
          ? {
              ...m,
              restrictions: { ...("restrictions" in m ? m.restrictions : {}), daily_minutes: 60 },
              bonus_minutes: 15,
            }
          : m,
      ),
    };
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/household") return json(200, household);
      if (path === "/api/v1/household/requests") return json(200, []);
      if (request.method === "POST" && /\/profiles\/.+\/(minutes|free)$/.test(path)) {
        posted.push([path.split("/").at(-1) ?? "", await request.json()]);
        return json(204, null);
      }
      return json(404, {});
    };
    show(<HouseholdPage view="profiles" />);
    const tools = await screen.findByRole("region", { name: "Screen time" });
    expect(within(tools).getByText(/\+15 min today/)).toBeTruthy();
    fireEvent.click(within(tools).getByRole("button", { name: "+30 min" }));
    await waitFor(() => expect(posted).toEqual([["minutes", { minutes: 30 }]]));
    fireEvent.click(within(tools).getByRole("button", { name: "1 hour" }));
    await waitFor(() => expect(posted.at(-1)).toEqual(["free", { minutes: 60 }]));

    household = {
      ...HOUSEHOLD,
      members: HOUSEHOLD.members.map((m) =>
        m.id === LEA ? { ...m, free_until: new Date(Date.now() + 3_600_000).toISOString() } : m,
      ),
    };
    cleanup();
    show(<HouseholdPage view="profiles" />);
    const freed = await screen.findByRole("region", { name: "Screen time" });
    expect(within(freed).getByText(/No limits until/)).toBeTruthy();
    fireEvent.click(within(freed).getByRole("button", { name: "Limits back" }));
    await waitFor(() => expect(posted.at(-1)).toEqual(["free", { minutes: null }]));
  });

  it("keeps out any genre, plans spans of the week and shows titles above its age", async () => {
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/household") return json(200, HOUSEHOLD);
      if (path === "/api/v1/household/requests") return json(200, []);
      if (path === "/api/v1/media/facets")
        return json(200, { years: {}, genres: ["Science-Fiction", "Animation"] });
      return json(404, {});
    };
    show(<HouseholdPage view="profiles" />);
    fireEvent.click(await screen.findByRole("button", { name: "Edit Léa" }));
    const editor = await screen.findByRole("dialog", { name: "Edit Léa" });
    fireEvent.change(within(editor).getByLabelText(/Add a genre/), { target: { value: "Science-Fiction" } });
    fireEvent.click(within(editor).getByRole("button", { name: "Add" }));
    expect(within(editor).getByRole("button", { name: "Remove science fiction" })).toBeTruthy();
    fireEvent.click(within(editor).getByRole("button", { name: "Remove science fiction" }));
    expect(within(editor).queryByRole("button", { name: "Remove science fiction" })).toBeNull();

    fireEvent.click(within(editor).getByRole("button", { name: "Add a span on Saturday" }));
    expect(within(editor).getByRole("region", { name: "Span on Saturday" })).toBeTruthy();
    fireEvent.click(within(editor).getByRole("radio", { name: /^Shown(?! locked)/ }));
    expect(
      (within(editor).getByRole("radio", { name: /^Shown(?! locked)/ }) as HTMLInputElement).checked,
    ).toBe(true);
  });

  it("hides the master's tools from a profile", async () => {
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/household") return json(200, { ...HOUSEHOLD, me: LEA, can_manage: false });
      if (path === "/api/v1/household/requests") return json(200, []);
      return json(404, {});
    };
    show(<HouseholdPage view="profiles" />);
    expect(await screen.findByRole("button", { name: "My PIN" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Edit Léa" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Add a profile" })).toBeNull();
    expect(screen.getByRole("button", { name: "My PIN" })).toBeTruthy();
  });
});

describe("a locked title", () => {
  it("tells a request already waiting instead of asking again, and why it is locked", async () => {
    fake.handler = () => json(200, [REQUEST]);
    const problem = new ApiError(403, "restricted", "household.restricted", {
      object_id: REQUEST.subject_ref,
      name: "Hey Arnold!",
      rating: null,
      reason: "unrated",
      can_ask: true,
    });
    show(<LockedTitle problem={problem} />);
    expect(await screen.findByText(/waiting for the master's answer/)).toBeTruthy();
    expect(screen.getByText(/has no age rating yet/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Ask for access" })).toBeNull();
  });

  it("says when the profile cannot ask", () => {
    fake.handler = () => json(200, []);
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
      if (request.method === "GET") return json(200, []); // no request yet
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

describe("a title shown to a profile, never played (issue 432)", () => {
  it("says why and asks the master for access", async () => {
    const asked: unknown[] = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/household/requests" && request.method === "GET") return json(200, []);
      if (path === "/api/v1/household/requests") {
        asked.push(await request.json());
        return json(201, { id: "r1" });
      }
      return json(404, {});
    };
    show(
      <KeptNotice
        objectId={REQUEST.subject_ref}
        title="Alien"
        kept={{ rating: "16+", reason: "age", can_ask: true }}
      />,
    );
    expect(screen.getByRole("heading", { name: /Alien/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Ask for access" }));
    await waitFor(() =>
      expect(asked).toMatchObject([{ ref: REQUEST.subject_ref, title: "Alien", rating: "16+" }]),
    );
  });
});
