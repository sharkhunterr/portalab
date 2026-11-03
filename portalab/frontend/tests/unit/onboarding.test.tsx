import * as DialogPrimitive from "@radix-ui/react-dialog";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// #7 — the member onboarding: the welcome opens once (and never again once seen, on any device, or when the
// administrator turned it off); the first steps list the discovery missions with what they bring and go
// away when put away; the guided tour shows what is on screen and its end completes the « tour » step.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { startTour } from "../../src/features/onboarding/api";
import { FirstSteps } from "../../src/features/onboarding/FirstSteps";
import GuidePage from "../../src/features/onboarding/GuidePage";
import { TOUR_TIMING, Tour } from "../../src/features/onboarding/Tour";
import { TOURS } from "../../src/features/onboarding/tours";
import { WelcomeFlow } from "../../src/features/onboarding/WelcomeFlow";
import { Notify } from "../../src/features/onboarding/WelcomeSteps";
import { BUNDLED } from "../../src/i18n/bundled";
import { json, ME } from "../support/fake-api";

function show(element: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([{ path: "*", element }]); // the tours open their pages
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

interface Backend {
  preferences?: Array<{ key: string; value: unknown }>;
  welcome?: { enabled: boolean; message: string };
  quests?: unknown[];
  assistant?: boolean;
}

function backend({
  preferences = [],
  welcome = { enabled: true, message: "" },
  quests = [],
  assistant = false,
}: Backend) {
  const puts: Array<Record<string, unknown>> = [];
  const posts: string[] = [];
  const visibility: Array<[string, unknown]> = [];
  const resets: string[] = []; // issue 347: the home made to the member's tastes
  fake.handler = async (request) => {
    const path = new URL(request.url).pathname;
    if (request.method === "PUT" && path === "/api/v1/me/preferences") {
      puts.push(await request.json());
      return json(200, { preferences: [] });
    }
    if (request.method === "PUT" && path.startsWith("/api/v1/me/privacy/visibility/")) {
      const { level } = (await request.json()) as { level: string };
      visibility.push([path.split("/").pop() ?? "", level]);
      return json(200, { effective: true });
    }
    if (request.method === "POST") {
      posts.push(path);
      if (path === "/api/v1/dashboard/reset") resets.push(await request.text());
      return json(200, []);
    }
    if (path === "/api/v1/me") return json(200, ME);
    if (path === "/api/v1/me/preferences") return json(200, { preferences });
    if (path === "/api/v1/me/onboarding/welcome") return json(200, welcome);
    if (path === "/api/v1/me/quests") return json(200, quests);
    if (path === "/api/v1/ai/status")
      return json(200, {
        available: assistant,
        provider_state: assistant ? "ok" : "disabled",
        auto_navigate: false,
      });
    return json(404, {});
  };
  return { puts, posts, visibility, resets };
}

const mission = (key: string, done = false) => ({
  key,
  kind: "discovery",
  label: key,
  icon: "user",
  completed_at: done ? "2026-10-10T10:00:00Z" : null,
  rewards: [
    { value: "xp", amount: 25 },
    { value: "coins", amount: 10 },
  ],
  steps: [{ current: done ? 1 : 0, target: 1 }],
});

describe("welcome", () => {
  it("opens on a first visit, with the portal's words, and skipping it is remembered", async () => {
    window.localStorage.clear();
    const { puts } = backend({ welcome: { enabled: true, message: "Have fun, folks" } });
    show(<WelcomeFlow />);
    expect(await screen.findByRole("heading", { name: "Welcome, Alice!" })).toBeInTheDocument();
    expect(screen.getByText("Have fun, folks")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Let's go" }));
    expect(await screen.findByRole("heading", { name: "A face and a name" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    await waitFor(() => expect(puts.flatMap(Object.keys)).toContain("shell.onboarding.welcomedAt"));
    expect(screen.queryByRole("heading", { name: "A face and a name" })).toBeNull();
  });

  it("stays closed once seen elsewhere, or when the administrator turned it off", async () => {
    window.localStorage.clear();
    backend({ preferences: [{ key: "shell.onboarding.welcomedAt", value: "2026-10-09T10:00:00Z" }] });
    const first = show(<WelcomeFlow />);
    await waitFor(() => expect(fake.handler).toBeDefined());
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByRole("heading", { name: "Welcome, Alice!" })).toBeNull();
    first.unmount();

    backend({ welcome: { enabled: false, message: "" } });
    show(<WelcomeFlow />);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByRole("heading", { name: "Welcome, Alice!" })).toBeNull();
  });

  it("keeps what the member came for", async () => {
    window.localStorage.clear();
    const { puts, posts } = backend({});
    show(<WelcomeFlow />);
    fireEvent.click(await screen.findByRole("button", { name: "Let's go" }));
    await screen.findByRole("heading", { name: "A face and a name" });
    fireEvent.click(screen.getByRole("button", { name: "Next" })); // profile unchanged
    await screen.findByRole("heading", { name: "Your media accounts" }); // issue 347
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByRole("heading", { name: "How far do you want to play?" });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByRole("heading", { name: "Your portal, to your taste" });
    fireEvent.click(screen.getByRole("checkbox", { name: "Films" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Retro video games" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByRole("heading", { name: "How should we tell you?" })).toBeInTheDocument();
    await waitFor(() =>
      expect(puts).toContainEqual({ "shell.onboarding.interests": ["movies", "retro_games"] }),
    );
    expect(posts).toContain("/api/v1/me/onboarding/interests/complete");
  });

  // issue 243: a player is public within the portal; one who does not play is anonymous to the other members.
  // Issue 347: a notch of the play gauge, the dashboard made for it on a first visit, then how they are told.
  it.each([
    ["Passive", "progression", "community"],
    ["Just the media", "none", "private"],
  ])("« %s » keeps the choice and sets who sees the member", async (answer, play, level) => {
    window.localStorage.clear();
    const { puts, resets, visibility } = backend({});
    show(<WelcomeFlow />);
    fireEvent.click(await screen.findByRole("button", { name: "Let's go" }));
    await screen.findByRole("heading", { name: "A face and a name" });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByRole("heading", { name: "Your media accounts" });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(await screen.findByRole("button", { name: answer }));
    expect(screen.getByRole("slider", { name: "How much you play" })).toHaveAttribute(
      "aria-valuetext",
      answer,
    );
    expect(
      screen.getByText(level === "private" ? /will be anonymous/ : /will be public/),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    // the portal to their taste: the game ticked for a player, out of reach for one who does not play
    await screen.findByRole("heading", { name: "Your portal, to your taste" });
    const game = screen.getByRole("checkbox", { name: "Play" });
    expect(game).toHaveProperty("checked", play !== "none");
    expect(game).toHaveProperty("disabled", play === "none");
    fireEvent.click(screen.getByRole("checkbox", { name: "The radio" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByRole("heading", { name: "How should we tell you?" })).toBeInTheDocument();
    // a first visit: the home made at once, from the profile's dashboard, to these tastes
    const tastes = [
      "watch",
      "releases",
      "news",
      "requests",
      ...(play === "none" ? [] : ["play"]),
      "services",
      "radio",
    ];
    expect(resets.map((body) => JSON.parse(body))).toEqual([{ tastes }]);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByRole("heading", { name: "Your look" })).toBeInTheDocument();
    expect(visibility).toEqual(
      expect.arrayContaining([
        ["progression", level],
        ["member_listing", level],
        ["community_activity", level],
      ]),
    );
    await waitFor(() => expect(puts).toContainEqual({ "shell.onboarding.play": play }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByRole("heading", { name: "All set, Alice!" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Notifications and e-mails/ })).toHaveAttribute(
      "href",
      "/settings/notifications",
    );
  });
});

describe("first steps", () => {
  it("lists the missions with their rewards and can be put away", async () => {
    window.localStorage.clear();
    const { puts } = backend({
      quests: [mission("discover_profile", true), mission("discover_tour"), mission("daily", false)].map(
        (m, i) => (i === 2 ? { ...m, kind: "daily" } : m),
      ),
    });
    show(<FirstSteps />);
    expect(await screen.findByRole("heading", { name: "First steps" })).toBeInTheDocument();
    expect(screen.getByText("Make your profile yours")).toBeInTheDocument();
    expect(screen.getByText("Take the tour")).toBeInTheDocument();
    expect(screen.getByText("+25 XP · +10 Coins")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "1 of 2 done" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Put away the first steps" }));
    await waitFor(() => expect(puts.flatMap(Object.keys)).toContain("shell.onboarding.stepsHiddenAt"));
    expect(screen.queryByRole("heading", { name: "First steps" })).toBeNull();
  });

  it("goes away once every mission is done", async () => {
    window.localStorage.clear();
    backend({ quests: [mission("discover_profile", true), mission("discover_tour", true)] });
    const { container } = show(<FirstSteps />);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container.querySelector(".first-steps")).toBeNull();
  });
});

describe("guided tour", () => {
  it("has its words for every step of every tour", () => {
    const messages = BUNDLED.onboarding as Record<string, string>;
    for (const tour of TOURS) {
      expect(messages[`tours.${tour.key}.title`], tour.key).toBeTruthy();
      expect(messages[`tours.${tour.key}.description`], tour.key).toBeTruthy();
      expect(tour.steps.at(-1)?.targets, tour.key).toEqual([]); // each ends on a bubble of its own
      for (const step of tour.steps) {
        expect(messages[`tours.${tour.key}.${step.key}.title`], `${tour.key}.${step.key}`).toBeTruthy();
        expect(messages[`tours.${tour.key}.${step.key}.text`], `${tour.key}.${step.key}`).toBeTruthy();
      }
    }
  });

  it("leaves out what is not on screen and its end is said once", async () => {
    TOUR_TIMING.patience = 30;
    window.localStorage.clear();
    const { posts, puts } = backend({});
    show(<Tour />);
    act(() => startTour("services"));
    // nothing of the page is drawn here: only the closing bubble remains
    expect(await screen.findByRole("dialog", { name: "Something wrong?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Finish" }));
    await waitFor(() => expect(posts).toContain("/api/v1/me/onboarding/tours/services/complete"));
    expect(posts).not.toContain("/api/v1/me/onboarding/tour/complete");
    expect(puts).toContainEqual({ "shell.onboarding.toursSeen": ["services"] });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("the portal's tour also completes the welcome's tour step", async () => {
    TOUR_TIMING.patience = 30;
    const { posts } = backend({});
    show(<Tour />);
    act(() => startTour());
    fireEvent.click(await screen.findByRole("button", { name: "Finish" }));
    await waitFor(() => expect(posts).toContain("/api/v1/me/onboarding/tours/portal/complete"));
    expect(posts).toContain("/api/v1/me/onboarding/tour/complete");
  });

  it("leaves with Escape without completing anything", async () => {
    TOUR_TIMING.patience = 30;
    const { posts } = backend({});
    show(<Tour />);
    act(() => startTour("calendar"));
    await screen.findByRole("dialog", { name: "Never miss a thing" });
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(posts).toEqual([]);
  });
});

describe("guide", () => {
  it("offers every tour, with what its mission still brings", async () => {
    window.localStorage.clear();
    backend({
      preferences: [{ key: "shell.onboarding.toursSeen", value: ["services"] }],
      quests: [mission("discover_ticket")],
    });
    show(<GuidePage />);
    expect(await screen.findByRole("heading", { name: "Guided tours" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ask the support" })).toBeInTheDocument();
    expect(await screen.findByText("+25 XP · +10 Coins")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "See again : Service status" })).toBeInTheDocument();
    // issue 181: the assistant's tours only while it is switched on
    expect(screen.getAllByRole("heading", { level: 4 })).toHaveLength(
      TOURS.filter((tour) => !tour.requires).length - 1,
    );
    expect(screen.queryByRole("heading", { name: "The assistant" })).toBeNull();
  });

  it("offers the assistant's tours while it is on", async () => {
    window.localStorage.clear();
    backend({ assistant: true, quests: [mission("discover_assistant")] });
    show(<GuidePage />);
    expect(await screen.findByRole("heading", { name: "The assistant" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Power up the assistant" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 4 })).toHaveLength(TOURS.length - 1);
  });
});

// issue 347: how the member is told — a ready-made choice sets every switch they may turn, never a required one
describe("welcome: how to be told", () => {
  it("« The essentials » keeps everything on the portal and the e-mails for what matters", async () => {
    const sent: unknown[] = [];
    const channel = (enabled: boolean, mandatory = false) => ({ enabled, mandatory, locked: false });
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/me/notification-preferences" && request.method === "PUT") {
        sent.push(await request.json());
        return json(200, { categories: [], digest: "daily" });
      }
      if (path === "/api/v1/me/notification-preferences")
        return json(200, {
          digest: "off",
          categories: [
            {
              key: "account.security",
              label_key: "x",
              channels: { portal: channel(true, true), email: channel(true, true) },
            },
            {
              key: "media.available",
              label_key: "x",
              channels: { portal: channel(false), email: channel(false) },
            },
            {
              key: "community.reply",
              label_key: "x",
              channels: { portal: channel(false), email: channel(true) },
            },
          ],
        });
      return json(404, {});
    };
    show(
      <DialogPrimitive.Root open>
        <DialogPrimitive.Content aria-describedby={undefined}>
          <Notify titleId="t" nav={null} />
        </DialogPrimitive.Content>
      </DialogPrimitive.Root>,
    );
    await screen.findByRole("table"); // the switches, once the preferences are read
    fireEvent.click(screen.getByRole("radio", { name: /The essentials/ }));
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toEqual({
      digest: "daily",
      preferences: {
        "media.available": { portal: true, email: true },
        "community.reply": { portal: true, email: false },
      },
    });
  });
});
