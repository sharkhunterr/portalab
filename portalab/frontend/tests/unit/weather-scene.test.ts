import { describe, expect, it } from "vitest";
import {
  CONDITIONS,
  fallbackOf,
  moonPhase,
  sceneOf,
} from "../../src/design-system/themes/premium/weatherScene";

// #88 — the weather report as the « live weather » scene: each sky its own look, the hour's light at the
// place, the wind, the moon; the CSS stand-in of each weather.

describe("weather scene", () => {
  it("gives every weather a look of its own", () => {
    const looks = CONDITIONS.map((condition) =>
      JSON.stringify({ ...sceneOf({ condition, phase: "day" }), moon: 0 }),
    );
    expect(new Set(looks).size).toBe(CONDITIONS.length);
  });

  it("reads what falls, how hard, and whether it freezes", () => {
    const light = sceneOf({ condition: "rain", intensity: "light", phase: "day" });
    const heavy = sceneOf({ condition: "rain", intensity: "heavy", phase: "day" });
    expect(heavy.rain).toBeGreaterThan(light.rain);
    expect(sceneOf({ condition: "drizzle", phase: "day" }).drizzle).toBe(1);
    expect(sceneOf({ condition: "freezing_rain", phase: "day" }).ice).toBeGreaterThan(0.5);
    expect(sceneOf({ condition: "storm_hail", phase: "day" }).hail).toBeGreaterThan(0);
    expect(sceneOf({ condition: "storm", phase: "day" }).bolt).toBeGreaterThan(0);
    expect(sceneOf({ condition: "snow_grains", phase: "day" }).grains).toBe(1);
    expect(sceneOf({ condition: "showers", phase: "day" }).burst).toBe(1);
    expect(sceneOf({ condition: "fog", phase: "day" }).fog).toBeGreaterThan(0.5);
  });

  it("follows the light of the hour at the place, and the clouds it reports", () => {
    expect(sceneOf({ condition: "clear", phase: "day" }).light).toBe(1);
    expect(sceneOf({ condition: "clear", phase: "night" }).light).toBe(0);
    const dawn = sceneOf({ condition: "clear", phase: "dawn" });
    const dusk = sceneOf({ condition: "clear", phase: "dusk" });
    expect([dawn.glow, dawn.dawn, dusk.glow, dusk.dawn]).toEqual([1, 1, 1, 0]);
    // a partly cloudy night at 75 %: more cloud than the code alone says (#88's report)
    const reported = sceneOf({ condition: "partly_cloudy", phase: "night", cloud_cover: 75 });
    expect(reported.cloud).toBeGreaterThan(sceneOf({ condition: "partly_cloudy", phase: "night" }).cloud);
    expect(sceneOf({ condition: "overcast", phase: "day", cloud_cover: 40 }).cloud).toBeGreaterThanOrEqual(
      0.85,
    );
  });

  it("blows with the wind, from where it comes", () => {
    const calm = sceneOf({ condition: "clear", phase: "day", wind_speed: 5 });
    const gale = sceneOf({ condition: "clear", phase: "day", wind_speed: 55, wind_direction: 270 });
    expect(calm.wind).toBe(0);
    expect(gale.wind).toBeGreaterThan(0.8);
    expect(gale.windDir).toBe(1); // from the west: to the right
    expect(sceneOf({ condition: "clear", phase: "day", wind_direction: 90 }).windDir).toBe(-1);
  });

  it("without a report, a clear sky at the device's hour", () => {
    expect(sceneOf(null, new Date(2026, 9, 15, 13)).light).toBe(1);
    expect(sceneOf(null, new Date(2026, 9, 15, 23)).light).toBe(0);
    expect(sceneOf({ condition: null }, new Date(2026, 9, 15, 2)).light).toBe(0);
  });

  it("knows the moon's phase", () => {
    expect(moonPhase(new Date(Date.UTC(2000, 0, 6, 18, 14)))).toBeCloseTo(0, 3); // a known new moon
    expect(moonPhase(new Date(Date.UTC(2000, 0, 21, 4, 40)))).toBeCloseTo(0.5, 1); // full the 21st
  });

  it("has a CSS stand-in for each weather", () => {
    expect(fallbackOf({ condition: "storm_hail" })).toBe("rain");
    expect(fallbackOf({ condition: "snow_grains" })).toBe("snow");
    expect(fallbackOf({ condition: "rime_fog" })).toBe("fog");
    expect(fallbackOf({ condition: "clear", phase: "night" })).toBe("starfield");
    expect(fallbackOf({ condition: "clear", phase: "day" })).toBe("bokeh");
  });
});
