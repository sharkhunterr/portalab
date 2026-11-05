import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 012 — profile sections render in independent frames (an unavailable section never hides the others),
// feed entries are localized text linking to the actor, and no social-graph control exists.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { Feed } from "../../../src/features/community/feed/Feed";
import { Directory } from "../../../src/features/community/members/Directory";
import { ProfilePage } from "../../../src/features/community/profile/ProfilePage";
import { json } from "../../support/fake-api";

const MEMBER = "01900000-0000-7000-8000-000000000042";

function show(path: string, pattern: string, element: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter([{ path: pattern, element }], { initialEntries: [path] })} />
    </QueryClientProvider>,
  );
}

describe("community", () => {
  it("renders each profile section in its own frame", async () => {
    fake.handler = () =>
      json(200, {
        id: MEMBER,
        display_name: "Ursula",
        sections: [
          {
            key: "identity",
            owner: "module:community",
            label_key: "community:section.identity",
            state: "available",
            data: { display_name: "Ursula" },
          },
          {
            key: "progression",
            owner: "module:community",
            label_key: "community:section.progression",
            state: "unavailable",
            data: {},
          },
          {
            key: "activity",
            owner: "module:community",
            label_key: "community:section.activity",
            state: "no-data",
            data: {},
          },
        ],
      });
    show(`/m/${MEMBER}`, "/m/:memberId", <ProfilePage />);
    expect(await screen.findByRole("heading", { level: 1, name: "Ursula" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "About" })).toBeTruthy();
    expect(screen.getByText("This section is temporarily unavailable.")).toBeTruthy();
    expect(screen.getByText("Nothing to show yet.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /follow|friend|message|like/i })).toBeNull();
  });

  it("shows a not-found message without revealing anything", async () => {
    fake.handler = () => json(404, { code: "community.member_not_found", title: "Not found" });
    show(`/m/${MEMBER}`, "/m/:memberId", <ProfilePage />);
    expect(await screen.findByText("This profile does not exist or is not visible to you.")).toBeTruthy();
  });

  it("renders feed entries as localized text linking to the actor", async () => {
    fake.handler = () =>
      json(200, {
        items: [
          {
            id: "e1",
            actor_id: MEMBER,
            actor_name: "Ursula",
            kind: "achievement.unlocked",
            text_key: "community:feed.achievement.unlocked",
            params: { achievement: "first-steps" },
            subject_ref: null,
            source_event_id: "s1",
            occurred_at: "2026-10-01T12:00:00Z",
          },
        ],
        next_cursor: null,
      });
    show("/", "/", <Feed />);
    const link = await screen.findByRole("link", { name: "Ursula" });
    expect(link.getAttribute("href")).toBe(`/community/members/${MEMBER}`);
    expect(screen.getByText(/unlocked the achievement first-steps/)).toBeTruthy();
  });

  it("names an anonymous actor without a link nor a photo (issue 120)", async () => {
    fake.handler = () =>
      json(200, {
        items: [
          {
            id: "e2",
            actor_id: "01900000-0000-5000-8000-0000000000aa",
            actor_name: null,
            anonymous: true,
            kind: "user.level_up",
            text_key: "community:feed.user.level_up",
            params: { level: 4 },
            subject_ref: null,
            source_event_id: "s2",
            occurred_at: "2026-10-01T12:00:00Z",
          },
        ],
        next_cursor: null,
      });
    show("/", "/", <Feed />);
    expect(await screen.findByText("An anonymous member")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "An anonymous member" })).toBeNull();
    expect(document.querySelector(".community-timeline img")).toBeNull();
  });
});

describe("leaderboard table", () => {
  it("highlights the viewer in text and states their position", async () => {
    const { Leaderboard } = await import("../../../src/features/gamification/leaderboards/Leaderboard");
    const me = { rank: 2, user_id: "u2", display_name: "Ulrich", score: 20, me: true };
    render(
      <RouterProvider
        router={createMemoryRouter([
          {
            path: "/",
            element: (
              <Leaderboard
                caption="Leaderboard"
                rows={[{ rank: 1, user_id: "u1", display_name: "Ursula", score: 60, me: false }, me]}
                me={me}
                profileLinks
              />
            ),
          },
        ])}
      />,
    );
    expect(screen.getByRole("table")).toBeTruthy();
    const ursula = screen.getByRole("link", { name: /Ursula/ });
    expect(ursula.getAttribute("href")).toBe("/community/members/u1");
    expect(ursula.querySelector(".rank-who, [class*='avatar']") ?? ursula.firstElementChild).toBeTruthy(); // issue 177
    expect(screen.getByRole("link", { name: /Ulrich \(you\)/ }).getAttribute("href")).toBe(
      "/community/members/u2", // issue 177: mine too, as on the podium
    );
    expect(screen.getByText("Your position: #2 (20)")).toBeTruthy();
  });

  it("closes the directory with the anonymous members, nameless and unlinked (issue 347)", async () => {
    fake.handler = () =>
      json(200, {
        items: [{ id: MEMBER, display_name: "Mona", joined_at: "2026-10-01T12:00:00Z", look: null }],
        next_cursor: null,
        anonymous: 2,
      });
    show("/", "/", <Directory />);
    expect(await screen.findByRole("link", { name: /Mona/ })).toBeTruthy();
    expect(screen.getAllByText("Anonymous")).toHaveLength(2);
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });
});
