import { describe, expect, it } from "vitest";
import { isStaleBuildError } from "../../src/shell/staleBuild";

// #68 — a page left open across a deployment asks for code of the previous build: such failures are
// recognised (and reload the page once), other errors are shown as they are.

describe("stale build", () => {
  it("recognises a code file of a previous build failing to load", () => {
    expect(
      isStaleBuildError(new TypeError("Failed to fetch dynamically imported module: /assets/x.js")),
    ).toBe(true);
    expect(isStaleBuildError(new TypeError("Importing a module script failed."))).toBe(true);
    expect(isStaleBuildError(new Error("Cannot read properties of undefined"))).toBe(false);
  });
});
