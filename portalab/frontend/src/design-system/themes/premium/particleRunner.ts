import type { Container, ISourceOptions } from "@tsparticles/engine";
import { motionBudget, stillFor } from "../../motion/budget";

/**
 * #68: the particle ambiences, by tsParticles (MIT) — loaded only when one is chosen. Transparent, at 30
 * frames a second, never sounds (the fireworks preset fetches explosion sounds from another site: off).
 */
const COMMON: ISourceOptions = {
  fullScreen: { enable: false },
  background: { color: "transparent" },
  fpsLimit: 30,
  detectRetina: false,
  pauseOnBlur: true,
  pauseOnOutsideViewport: true,
};

const OPTIONS: Record<string, ISourceOptions> = {
  // driving snow in gusts: big flakes near, small far away
  blizzard: {
    ...COMMON,
    particles: {
      number: { value: 260, density: { enable: true } },
      color: { value: "#ffffff" },
      shape: { type: "circle" },
      opacity: { value: { min: 0.25, max: 0.9 } },
      size: { value: { min: 0.8, max: 3.6 } },
      move: {
        enable: true,
        direction: "bottom-right",
        speed: { min: 3, max: 11 },
        straight: false,
        random: true,
        drift: { min: -1, max: 3 },
        outModes: { default: "out" },
      },
    },
  },
  // rockets rising from the bottom and bursting
  fireworks: {
    ...COMMON,
    preset: "fireworks",
    sounds: { enable: false },
  } as ISourceOptions,
  // a constellation of points, linked when near, drifting; the pointer pulls the links to it
  mesh: {
    ...COMMON,
    particles: {
      number: { value: 95, density: { enable: true } },
      color: { value: ["#7c9cff", "#b36bff", "#4fd1c5"] },
      shape: { type: "circle" },
      opacity: { value: { min: 0.4, max: 0.85 } },
      size: { value: { min: 1, max: 3 } },
      links: { enable: true, distance: 160, color: "#9fb4ff", opacity: 0.55, width: 1.2 },
      move: { enable: true, speed: 0.8, outModes: { default: "bounce" } },
    },
    interactivity: {
      detectsOn: "window",
      events: { onHover: { enable: true, mode: "grab" } },
      modes: { grab: { distance: 180, links: { opacity: 0.7 } } },
    },
  },
};

let engineReady: Promise<typeof import("@tsparticles/engine")> | null = null;

async function engine(kind: string) {
  engineReady ??= (async () => {
    const module = await import("@tsparticles/engine");
    const { loadSlim } = await import("@tsparticles/slim");
    await loadSlim(module.tsParticles);
    return module;
  })();
  const module = await engineReady;
  if (kind === "fireworks") {
    const { loadFireworksPreset } = await import("@tsparticles/preset-fireworks");
    await loadFireworksPreset(module.tsParticles);
  }
  return module.tsParticles;
}

/** Start a particle ambience in ``element``; resolves to its ``stop``, or ``null`` when unknown. */
export async function runParticles(element: HTMLElement, kind: string): Promise<(() => void) | null> {
  const options = OPTIONS[kind];
  if (!options) return null;
  const particles = await engine(kind);
  // #29: half the frames when saving; frozen when motion is « none »
  const budget = motionBudget();
  const container: Container | undefined = await particles.load({
    id: `ambient-${kind}-${Math.random().toString(36).slice(2)}`,
    element,
    options: budget === "eco" ? { ...options, fpsLimit: 15 } : options,
  });
  if (budget === "still" || stillFor(element)) window.setTimeout(() => container?.pause(), 400);
  return () => container?.destroy();
}
