import { describe, expect, it } from "vitest";
import { FEATURES } from "../../../src/features/admin/arrival/features";
import { STEPS } from "../../../src/features/admin/setup/progress";

// Issue 453 — the setup assistant knows the households: a step of their own (profiles per account, the
// charts' grouping), the system language in its card (not raw settings), households among the features.

describe("the setup assistant", () => {
  it("has a step for the households, after the members", () => {
    const keys = STEPS.map((step) => step.key);
    expect(keys.indexOf("household")).toBe(keys.indexOf("members") + 1);
    const household = STEPS.find((step) => step.key === "household");
    expect(household?.settings).toEqual(["household.maxProfiles", "economy.household.grouped"]);
  });

  it("sets the system language in its own card, not among raw settings", () => {
    const identity = STEPS.find((step) => step.key === "identity");
    expect(identity?.settings).not.toContain("i18n.systemLanguage");
    expect(identity?.settings).toContain("i18n.defaultTimeZone");
  });

  it("offers households among the portal's features", () => {
    expect(FEATURES.find((feature) => feature.key === "household")?.modules).toEqual(["household"]);
  });
});
