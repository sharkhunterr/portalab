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
  it("shows the sky outside: a storm, rain, snow, fog, a clear day or night", async () => {
    const { weatherAmbient } = await import("../../src/design-system/themes/premium/WeatherAmbient");
    expect(weatherAmbient({ condition: "storm", is_day: true })).toBe("thunderstorm");
    expect(weatherAmbient({ condition: "rain", is_day: true })).toBe("downpour");
    expect(weatherAmbient({ condition: "snow", is_day: false })).toBe("blizzard");
    expect(weatherAmbient({ condition: "cloudy", is_day: true })).toBe("fog");
    expect(weatherAmbient({ condition: "clear", is_day: true })).toBe("forest");
    expect(weatherAmbient({ condition: "clear", is_day: false })).toBe("cosmos");
    expect(weatherAmbient(null)).toBe("starfield"); // no place set yet
  });
});
