import { render, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AmbientLayer } from "../../src/design-system/themes/AmbientLayer";
import { isPremiumAmbient, PREMIUM_FALLBACK } from "../../src/design-system/themes/premium/PremiumAmbient";

// #68 — premium ambiences drawn on a canvas; when the device cannot (no WebGL, as here), the CSS ambience
// standing for each shows instead — never an empty page.

describe("premium ambiences", () => {
  it("knows which ambiences are drawn on a canvas, each with a CSS stand-in", () => {
    for (const kind of ["inferno", "thunderstorm", "sandstorm", "matrix", "fireworks", "mesh"]) {
      expect(isPremiumAmbient(kind)).toBe(true);
      expect(PREMIUM_FALLBACK[kind]).toBeTruthy();
    }
    expect(isPremiumAmbient("snow")).toBe(false);
  });

  it("falls back to the CSS ambience without WebGL", async () => {
    render(<AmbientLayer kind="inferno" />);
    await waitFor(() => expect(document.querySelector('[data-ambient="embers"]')).not.toBeNull());
    expect(document.querySelector('[data-ambient="inferno"]')).toBeNull();
  });
});

describe("live weather ambience", () => {
  it("draws its own sky, the CSS ambience of that weather standing in without WebGL", async () => {
    const { WeatherAmbient } = await import("../../src/design-system/themes/premium/WeatherAmbient");
    render(
      <WeatherAmbient
        contained
        report={{ condition: "snow_showers", intensity: "heavy", phase: "night" }}
        fallback={(kind) => <AmbientLayer kind={kind as "snow"} contained />}
      />,
    );
    await waitFor(() => expect(document.querySelector('[data-ambient="snow"]')).not.toBeNull());
  });
});
