import { type CSSProperties, memo } from "react";
import type { Ambient } from "../a11y/preferences";
import "./ambient.css";
import { isPremiumAmbient, PREMIUM_FALLBACK, PremiumAmbient } from "./premium/PremiumAmbient";
import { WeatherAmbient } from "./premium/WeatherAmbient";

/**
 * Ambient layer (027): an animated decoration behind the content — snow, embers, code rain, fireflies,
 * stars, petals, bats, bubbles, neon rain, a disco ball's lights… Chosen by the theme (``background.ambient``)
 * or by the member (``ui.ambient``, some sold in the shop), and reused as a profile's animated background.
 * Purely decorative (``aria-hidden``, no pointer events), drawn with CSS transforms only; nothing at all
 * under reduced motion or high contrast (the caller passes ``none``).
 */
const COUNTS: Partial<Record<Ambient, number>> = {
  snow: 46,
  embers: 30,
  "code-rain": 22,
  fireflies: 24,
  starfield: 70,
  warp: 36,
  petals: 24,
  bats: 9,
  bubbles: 24,
  rain: 60,
  sparkles: 30,
  disco: 7,
  fog: 5,
  sand: 50,
  leaves: 20,
  hearts: 18,
  glitch: 8,
  lights: 26,
  spores: 30,
  aurora: 3,
  vhs: 12,
  wind: 16,
  tide: 14,
  lanterns: 18,
  pixelsky: 40,
  upsidedown: 46,
  veins: 14,
  bokeh: 14,
  nostromo: 12,
  meadow: 60,
  ash: 50,
  // #81: the seasons
  cobwebs: 10,
  ornaments: 14,
  loveletters: 16,
  butterflies: 14,
  seagulls: 9,
  // #89: the universes
  floatingcandles: 16,
  cannonsmoke: 10,
  gears: 12,
  skyclouds: 9,
  silkwaves: 5,
  reactions: 18,
  equalizer: 28,
  cinemaglow: 4,
  pages: 7,
  lcdstars: 18,
  fallingblocks: 12,
  fleet: 15,
  ghosts: 6,
  spincoins: 12,
};

const GLYPHS = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿ0123456789ﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎ:.=*+-<>";

/** A deterministic pseudo-random sequence: the same layout on every render, no layout jumps. */
function random(seed: number): number {
  const x = Math.sin(seed * 9301 + 49297) * 233280;
  return x - Math.floor(x);
}

function particles(kind: Ambient, count: number) {
  return Array.from({ length: count }, (_, i) => {
    const r = (n: number) => random(i * 7 + n + kind.length * 13);
    const style = {
      "--x": `${(r(1) * 100).toFixed(2)}%`,
      "--y": `${(r(2) * 100).toFixed(2)}%`,
      "--size": (0.4 + r(3) * 0.9).toFixed(2),
      "--duration": `${(6 + r(4) * 12).toFixed(1)}s`,
      "--delay": `${(-r(5) * 18).toFixed(1)}s`,
      "--drift": `${((r(6) - 0.5) * 12).toFixed(1)}vw`,
      "--hue": Math.round(r(7) * 360),
      "--i": i,
    } as CSSProperties;
    const text =
      kind === "code-rain"
        ? Array.from(
            { length: 18 + Math.round(r(8) * 14) },
            (_, j) => GLYPHS[Math.floor(random(i * 31 + j) * GLYPHS.length)],
          ).join("")
        : null;
    return { key: `${kind}-${i}`, style, text };
  });
}

export const AmbientLayer = memo(function AmbientLayer({
  kind,
  contained = false,
}: {
  kind: Ambient;
  /** Inside a box (a profile background) instead of behind the whole page. */
  contained?: boolean;
}) {
  if (kind === "weather") {
    // #68: the ambience of the sky outside
    return <WeatherAmbient render={(sky) => <AmbientLayer kind={sky as Ambient} contained={contained} />} />;
  }
  if (isPremiumAmbient(kind)) {
    // #68: drawn on a canvas (shader or particles); the CSS ambience stands in when it cannot be
    const fallback = PREMIUM_FALLBACK[kind] as Ambient;
    return (
      <PremiumAmbient
        kind={kind}
        contained={contained}
        fallback={<AmbientLayer kind={fallback} contained={contained} />}
      />
    );
  }
  const count = COUNTS[kind];
  if (kind === "none" || !count) return null;
  return (
    <div className="ambient" data-ambient={kind} data-contained={contained || undefined} aria-hidden="true">
      {particles(kind, count).map((particle) => (
        <span key={particle.key} style={particle.style}>
          {particle.text}
        </span>
      ))}
    </div>
  );
});
