/**
 * #88: the weather report (``/api/v1/ui/weather``) as the « live weather » scene — how bright the hour is
 * (dawn, day, dusk, night), how much cloud and how dark, what falls (drizzle, rain, showers, snow, snow
 * grains, hail) and how hard, whether it freezes, the fog, the lightning, the wind and where it blows, the
 * moon's phase. Every number is 0..1 (``windDir`` ±1); the shader draws the mix, so each sky has its own look
 * and any blend of them is possible.
 */

export interface WeatherReport {
  condition: string | null;
  intensity?: string | null;
  is_day?: boolean;
  phase?: string | null;
  cloud_cover?: number | null;
  wind_speed?: number | null;
  wind_gusts?: number | null;
  wind_direction?: number | null;
  windy?: boolean;
  precipitation?: number | null;
  temperature?: number | null;
}

export interface Scene {
  light: number; // 0 night … 1 full day
  glow: number; // the low warm light of dawn and dusk
  dawn: number; // 1 dawn (pinker), 0 dusk (more orange)
  cloud: number; // how much of the sky is covered
  veil: number; // a thin veil of high clouds, the sun milky with a halo
  dark: number; // how heavy the clouds are
  rain: number;
  drizzle: number; // fine, slow drops instead of streaks
  burst: number; // showers: curtains coming and going, sun in between
  snow: number;
  grains: number; // snow grains: tiny and dense
  hail: number;
  ice: number; // freezing: frost on the edges, a cold tint
  fog: number;
  bolt: number; // lightning
  wind: number;
  windDir: number; // +1 blowing to the right, -1 to the left
  moon: number; // phase: 0 new, 0.5 full
}

/** Every sky the forecast may tell (the backend's ``condition``), in the order they are shown. */
export const CONDITIONS = [
  "clear",
  "mainly_clear",
  "partly_cloudy",
  "overcast",
  "fog",
  "rime_fog",
  "drizzle",
  "freezing_drizzle",
  "rain",
  "freezing_rain",
  "showers",
  "snow",
  "snow_grains",
  "snow_showers",
  "storm",
  "storm_hail",
  "hazy",
  "mist",
  "sleet",
  "windy",
] as const;
export type Condition = (typeof CONDITIONS)[number];

const STRENGTH: Record<string, number> = { light: 0.4, moderate: 0.7, heavy: 1 };

type Look = Partial<Omit<Scene, "light" | "glow" | "dawn" | "windDir" | "moon">>;
const LOOKS: Record<Condition, (k: number) => Look> = {
  clear: () => ({ cloud: 0.02 }),
  mainly_clear: () => ({ cloud: 0.22 }),
  partly_cloudy: () => ({ cloud: 0.5 }),
  overcast: () => ({ cloud: 0.95, dark: 0.35 }),
  fog: () => ({ cloud: 0.3, fog: 0.95 }),
  rime_fog: () => ({ cloud: 0.3, fog: 0.9, ice: 0.7 }),
  drizzle: (k) => ({ cloud: 0.88, dark: 0.3, rain: 0.25 + 0.35 * k, drizzle: 1, fog: 0.2 }),
  freezing_drizzle: (k) => ({
    cloud: 0.88,
    dark: 0.3,
    rain: 0.25 + 0.35 * k,
    drizzle: 1,
    ice: 0.8,
    fog: 0.15,
  }),
  rain: (k) => ({ cloud: 0.92, dark: 0.35 + 0.25 * k, rain: k }),
  freezing_rain: (k) => ({ cloud: 0.92, dark: 0.4, rain: k, ice: 0.9 }),
  showers: (k) => ({ cloud: 0.7, dark: 0.45 + 0.25 * k, rain: 0.35 + 0.65 * k, burst: 1 }),
  snow: (k) => ({ cloud: 0.92, dark: 0.15, snow: k, fog: 0.1 * k }),
  snow_grains: () => ({ cloud: 0.9, dark: 0.15, snow: 0.55, grains: 1 }),
  snow_showers: (k) => ({ cloud: 0.72, dark: 0.3, snow: 0.35 + 0.65 * k, burst: 1 }),
  storm: (k) => ({ cloud: 1, dark: 0.85, rain: 0.6 + 0.3 * k, bolt: 0.55 + 0.35 * k }),
  storm_hail: (k) => ({ cloud: 1, dark: 0.9, rain: 0.55, hail: 0.6 + 0.4 * k, bolt: 0.7 + 0.3 * k }),
  hazy: () => ({ cloud: 0.15, veil: 0.85 }),
  mist: () => ({ cloud: 0.35, fog: 0.42, veil: 0.3 }),
  sleet: (k) => ({ cloud: 0.92, dark: 0.35, rain: 0.3 + 0.35 * k, snow: 0.25 + 0.35 * k, fog: 0.1 }),
  windy: () => ({ cloud: 0.35, wind: 0.9 }),
};

const clamp = (n: number) => Math.min(1, Math.max(0, n));

/** The moon's phase on this date: 0 new, 0.5 full (a mean synodic month from a known new moon). */
export function moonPhase(at: Date = new Date()): number {
  const known = Date.UTC(2000, 0, 6, 18, 14);
  const days = (at.getTime() - known) / 86_400_000;
  const phase = (days / 29.530588853) % 1;
  return phase < 0 ? phase + 1 : phase;
}

export function isCondition(value: unknown): value is Condition {
  return typeof value === "string" && (CONDITIONS as readonly string[]).includes(value);
}

/** Without a report (no place yet): the hour of the device — dawn, day, dusk or night. */
export function phaseAt(at: Date): string {
  const h = at.getHours() + at.getMinutes() / 60;
  return h < 6.5 || h >= 20.5 ? "night" : h < 7.5 ? "dawn" : h >= 19.5 ? "dusk" : "day";
}

export function sceneOf(report: WeatherReport | null, at: Date = new Date()): Scene {
  // no weather (no place, the forecast unreachable): a clear sky at the device's hour
  const phase = report?.condition
    ? (report.phase ?? (report.is_day === false ? "night" : "day"))
    : phaseAt(at);
  const light = phase === "day" ? 1 : phase === "night" ? 0 : 0.5;
  const glow = phase === "dawn" || phase === "dusk" ? 1 : 0;
  const condition: Condition = isCondition(report?.condition) ? report.condition : "clear";
  const look = LOOKS[condition](STRENGTH[report?.intensity ?? "moderate"] ?? 0.7);
  // the forecast's own cover: the clear skies follow it; a falling sky stays at least as covered as it
  // looks; in fog the sky is not seen (the fog is drawn, not the clouds above it)
  const cover = typeof report?.cloud_cover === "number" ? clamp(report.cloud_cover / 100) : null;
  const precip = (look.rain ?? 0) + (look.snow ?? 0) > 0 || condition === "mist" || condition === "windy";
  const cloud =
    cover === null || condition === "fog" || condition === "rime_fog"
      ? (look.cloud ?? 0)
      : precip
        ? Math.max(look.cloud ?? 0, cover)
        : condition === "overcast"
          ? Math.max(0.85, cover)
          : 0.6 * cover + 0.4 * (look.cloud ?? 0);
  const speed = Math.max(report?.wind_speed ?? 0, (report?.wind_gusts ?? 0) * 0.7);
  const wind = Math.max(clamp((speed - 8) / 52), report?.windy ? 0.6 : 0, look.wind ?? 0);
  // meteorological direction: where it comes from — from the west (270°) it blows to the right
  const direction = report?.wind_direction;
  const windDir = typeof direction === "number" ? (Math.sin((direction * Math.PI) / 180) > 0 ? -1 : 1) : 1;
  return {
    light,
    glow,
    dawn: phase === "dawn" ? 1 : 0,
    cloud: clamp(cloud),
    veil: look.veil ?? 0,
    dark: look.dark ?? 0,
    rain: look.rain ?? 0,
    drizzle: look.drizzle ?? 0,
    burst: look.burst ?? 0,
    snow: look.snow ?? 0,
    grains: look.grains ?? 0,
    hail: look.hail ?? 0,
    ice: look.ice ?? 0,
    fog: look.fog ?? 0,
    bolt: look.bolt ?? 0,
    wind,
    windDir,
    moon: moonPhase(at),
  };
}

/** The CSS ambience standing in when the device cannot draw the scene. */
export function fallbackOf(report: WeatherReport | null): string {
  const condition = isCondition(report?.condition) ? report.condition : null;
  const night = report?.phase === "night" || report?.is_day === false;
  switch (condition) {
    case "storm":
    case "storm_hail":
    case "rain":
    case "freezing_rain":
    case "showers":
    case "drizzle":
    case "freezing_drizzle":
      return "rain";
    case "sleet":
    case "snow":
    case "snow_grains":
    case "snow_showers":
      return "snow";
    case "fog":
    case "rime_fog":
    case "mist":
      return "fog";
    case "windy":
      return "wind";
    case "overcast":
    case "partly_cloudy":
      return "skyclouds";
    case "hazy":
    case "mainly_clear":
    case "clear":
      return night ? "starfield" : "bokeh";
    default:
      return "starfield";
  }
}
