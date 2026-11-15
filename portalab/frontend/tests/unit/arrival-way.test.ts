import { describe, expect, it } from "vitest";
import { configureWay, initialSystem } from "../../src/features/admin/arrival/ArrivalWizard";
import { ALL_FEATURES } from "../../src/features/admin/arrival/features";

// Issue 249 — the wizard's steps signed in: the request quotas only once Seerr is connected (they are
// Seerr's own), play and the AI assistant only when their feature is kept.
describe("arrival wizard's way", () => {
  it("asks for the request quotas once Seerr is connected", () => {
    expect(configureWay(ALL_FEATURES)).not.toContain("quotas");
    expect(configureWay(ALL_FEATURES, true).slice(0, 3)).toEqual(["services", "quotas", "members"]);
  });
  it("leaves out play and the AI assistant when their feature is not kept", () => {
    const way = configureWay(new Set(["media", "wiki"]));
    expect(way).not.toContain("play");
    expect(way).not.toContain("ai");
    expect(way).toContain("appearance");
  });
  it("offers the browser's language and country as the system language (issue 438)", () => {
    expect(initialSystem("fr", "fr-CA")).toBe("fr-CA");
    expect(initialSystem("fr", "fr")).toBe("fr-FR"); // no country: the first offered for French
    expect(initialSystem("de", "en-US")).toBe("de-DE"); // the browser speaks another language
    expect(initialSystem("en", "en-gb")).toBe("en-GB");
    expect(initialSystem("xx", "")).toBe("en-US");
  });
});
