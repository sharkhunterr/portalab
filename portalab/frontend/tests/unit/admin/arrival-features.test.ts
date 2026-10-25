import { describe, expect, it } from "vitest";
import {
  ALL_FEATURES,
  type ModuleState,
  planFor,
  selectionOf,
  toggle,
} from "../../../src/features/admin/arrival/features";
import { loginFrom, type ServiceAccount } from "../../../src/features/admin/members/accounts";

// issue 246 — features chosen in the arrival wizard: what one needs comes with it, the modules switch in an
// order their dependencies accept, the kernel is never touched; logins made from services' accounts.

const mod = (key: string, enabled: boolean, requires: string[] = [], essential = false): ModuleState => ({
  key,
  enabled,
  requires,
  essential,
  needs_restart: false,
});

const MODULES = [
  mod("events", true, [], true),
  mod("content", true),
  mod("news", true, ["content"]),
  mod("wiki", false, ["content"]),
  mod("gamification", true, ["events"]),
  mod("marketplace", true, ["gamification"]),
  mod("community", true, ["gamification"]),
  mod("support", true, ["notifications"]),
];

describe("arrival features", () => {
  it("brings what a feature needs and takes what needs it", () => {
    const off = toggle(ALL_FEATURES, "play", false);
    expect(off.has("play") || off.has("shop")).toBe(false);
    const on = toggle(new Set(), "newsletter", true);
    expect([...on].sort()).toEqual(["news", "newsletter"]);
  });

  it("plans the modules in an order their dependencies accept, never the kernel", () => {
    const selection = toggle(toggle(ALL_FEATURES, "play", false), "tickets", false);
    const plan = planFor(selection, MODULES);
    expect(plan.enable).toEqual(["wiki"]);
    expect(plan.disable.indexOf("marketplace")).toBeLessThan(plan.disable.indexOf("gamification"));
    expect(plan.disable).not.toContain("events");
    expect(plan.disable).not.toContain("support"); // incidents still on
    expect(plan.settings).toContainEqual({ key: "support.tickets.enabled", value: false });
  });

  it("reads the features on from the modules and the switches", () => {
    const on = selectionOf(MODULES, [{ key: "news.newsletter.enabled", value: false }]);
    expect(on.has("news")).toBe(true);
    expect(on.has("newsletter")).toBe(false);
    expect(on.has("wiki")).toBe(false);
  });
});

describe("logins from accounts", () => {
  const account = (over: Partial<ServiceAccount>): ServiceAccount => ({
    external_id: "42",
    username: null,
    display_name: null,
    email: null,
    linked_user_id: null,
    verified: false,
    suggestion: null,
    unlinked_sessions: 0,
    ...over,
  });

  it("makes a login the portal accepts, numbered when taken", () => {
    expect(loginFrom(account({ username: "Jérémie D." }), new Set())).toBe("jeremie-d");
    expect(loginFrom(account({ username: "Bob" }), new Set(["bob"]))).toBe("bob-2");
    expect(loginFrom(account({ email: "zo@example.org" }), new Set())).toBe("zo-42");
    expect(loginFrom(account({}), new Set())).toMatch(/^[a-z0-9][a-z0-9._-]{2,}$/);
  });
});
