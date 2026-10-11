import { describe, expect, it } from "vitest";
import { badgesOf, KIND_ICONS } from "../../src/features/search/presentation";

// #67 — a result's type and state as badges: words first (translated, or the raw value when unknown),
// the tone only underlining them; every source has its icon.

const t = ((key: string) => key.split(":").slice(1).join(":")) as never;

describe("search result badges", () => {
  it("gives a title its type and state", () => {
    const badges = badgesOf(t, { kind: "media", facets: { type: "movie", status: "requested" } });
    expect(badges.map((b) => b.tone)).toEqual(["neutral", "warn"]);
    expect(badges[0]?.label).toBe("kind.movie");
  });

  it("names an unknown state as it is, without a tone", () => {
    const [badge] = badgesOf(t, { kind: "tickets", facets: { state: "waiting_for_parts" } });
    expect(badge).toEqual({ label: "waiting for parts", tone: "neutral" });
  });

  it("tells severity apart and knows every source's icon", () => {
    const badges = badgesOf(t, {
      kind: "incident",
      facets: { state: "investigating", severity: "critical" },
    });
    expect(badges.map((b) => b.tone)).toEqual(["warn", "bad"]);
    for (const kind of ["media", "wiki", "news", "tickets", "product", "member", "services"]) {
      expect(KIND_ICONS[kind]).toBeTruthy();
    }
  });
});
