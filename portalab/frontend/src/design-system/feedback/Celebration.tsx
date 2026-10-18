import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useAnnounce } from "../a11y/Announce";
import { FxLayer } from "../components/Fx";
import { Icon } from "../components/Icon";
import { sound } from "../sound/SoundService";
import { useTheme } from "../themes/ThemeProvider";
import { ExternalScript } from "../visuals/ExternalScript";
import { gpuLook, useGpuLook } from "../visuals/gpu";
import { externalLook } from "../visuals/registry";
import "../themes/celebration.css";

/**
 * Celebrations (spec 027 FR-007, R17): rewards and level-ups are acknowledged by a short, non-blocking
 * effect in the theme's style (``data-celebration``: sparkle, confetti, glow). At most one plays at a time
 * and at most one waits — further events are coalesced into the waiting one. Reduced motion replaces the
 * effect with a static badge; sounds follow the sound preference through ``SoundService``. The effect is
 * ``aria-hidden``; the message is announced politely.
 */

export interface CelebrationEvent {
  kind: "reward" | "level";
  /** Short visible text, e.g. "+40 XP" or "Level 5!". */
  text: string;
}

/** Coalescing queue: one playing, at most one pending; a pending level-up wins over rewards. */
export class CelebrationQueue {
  current: CelebrationEvent | null = null;
  pending: CelebrationEvent | null = null;

  push(event: CelebrationEvent): void {
    if (!this.current) {
      this.current = event;
      return;
    }
    if (this.pending?.kind === "level" && event.kind !== "level") return; // a waiting level-up wins
    this.pending = event; // newer replaces older: one effect for a burst of gains
  }

  next(): CelebrationEvent | null {
    this.current = this.pending;
    this.pending = null;
    return this.current;
  }
}

type Celebrate = (event: CelebrationEvent) => void;
const CelebrationContext = createContext<Celebrate>(() => {});

export function useCelebrate(): Celebrate {
  return useContext(CelebrationContext);
}

const DURATION_MS = { reward: 2000, level: 3000 } as const;

/**
 * 027: each celebration has its own particles, motion and badge — sparkles twinkle around the badge,
 * confetti and coins rain down, snow and petals drift down, hearts and bubbles rise, stars burst, bats fly
 * away, pixels explode on a grid, lightning flashes, glow pulses. Decorative only.
 */
const EFFECTS: Record<string, { count: number; icon?: string; layer: "badge" | "screen" }> = {
  sparkle: { count: 14, icon: "sparkle", layer: "badge" },
  confetti: { count: 40, layer: "screen" },
  glow: { count: 0, layer: "badge" },
  snow: { count: 34, icon: "snowflake", layer: "screen" },
  bats: { count: 12, layer: "badge" },
  pixels: { count: 36, layer: "badge" },
  hearts: { count: 18, icon: "heart", layer: "screen" },
  stars: { count: 16, icon: "star", layer: "badge" },
  coins: { count: 28, icon: "coins", layer: "screen" },
  lightning: { count: 4, icon: "zap", layer: "screen" },
  petals: { count: 26, layer: "screen" },
  bubbles: { count: 22, layer: "screen" },
  // the bubble itself plays: pixels rain down and build it, it burns, shatters, freezes, glitches, opens
  assemble: { count: 48, layer: "badge" },
  burn: { count: 16, icon: "flame", layer: "badge" },
  shatter: { count: 20, layer: "badge" },
  freeze: { count: 12, icon: "snowflake", layer: "badge" },
  glitch: { count: 10, layer: "badge" },
  portal: { count: 22, layer: "badge" },
  // 027: Christmas lights flickering round the bubble; fireworks bursting over the page
  flicker: { count: 12, layer: "badge" },
  fireworks: { count: 36, layer: "screen" },
  // 027: a tape rewinding (tracking bars racing across); soft colour blooms opening like a phone's wallpaper
  rewind: { count: 10, layer: "screen" },
  bloom: { count: 12, layer: "screen" },
  // 027: the motion tracker — echoes widening from the bubble, blips lighting up around it
  tracker: { count: 10, layer: "badge" },
  // #81: the seasons — sweets raining down, presents and Cupid's arrows bursting out, painted eggs bouncing
  // up, sea water splashing
  candy: { count: 26, layer: "screen" },
  gifts: { count: 14, layer: "badge" },
  cupid: { count: 10, layer: "badge" },
  eggs: { count: 18, layer: "screen" },
  splash: { count: 26, layer: "badge" },
  // #89: the universes — a wand's sparks, cannonballs, nuts and bolts
  wandsparks: { count: 24, layer: "badge" },
  cannonball: { count: 12, layer: "badge" },
  bolts: { count: 18, layer: "badge" },
  // #89: playing cards cascading, balloons rising, thumbs up popping
  cardcascade: { count: 14, layer: "screen" },
  balloons: { count: 14, layer: "screen" },
  likes: { count: 20, icon: "thumbs-up", layer: "badge" },
  // #89: music notes, red ribbons streaking, ink stamps
  musicnotes: { count: 18, icon: "music", layer: "badge" },
  ribbons: { count: 12, layer: "screen" },
  inkstamp: { count: 6, layer: "screen" },
  // #89: 8-bit hearts, lines clearing, laser shots
  pixelhearts: { count: 16, layer: "badge" },
  lineclear: { count: 8, layer: "screen" },
  lasers: { count: 14, layer: "badge" },
  pellets: { count: 16, layer: "badge" },
  coinpop: { count: 10, layer: "badge" },
  // #89: flower power, seashells, songbirds
  flowerpower: { count: 14, layer: "badge" },
  seashells: { count: 14, layer: "badge" },
  songbirds: { count: 10, layer: "screen" },
  // issue 130: the cosmos
  comets: { count: 12, layer: "badge" },
  planets: { count: 12, layer: "badge" },
};
const GRID = 12; // assemble: the bubble is built from a 12 × 4 grid of pixels

function seeded(i: number, n: number): number {
  const x = Math.sin(i * 12.9898 + n * 78.233) * 43758.5453;
  return x - Math.floor(x);
}

export function CelebrationProvider({ children }: { children: ReactNode }) {
  const queue = useRef(new CelebrationQueue());
  const [shown, setShown] = useState<CelebrationEvent | null>(null);
  const announce = useAnnounce();
  const { effective, looks } = useTheme();
  const reduced = effective.reducedMotion;

  const celebrate = useCallback<Celebrate>((event) => {
    const idle = queue.current.current === null;
    queue.current.push(event);
    if (idle) setShown(queue.current.current);
  }, []);

  useEffect(() => {
    if (!shown) return;
    announce(shown.text);
    void sound.play(shown.kind === "level" ? "levelUp" : "reward");
    // #78: a celebration drawn by the GPU plays a little longer (its scene needs the time)
    // issue 1: an imported one says how long it plays
    const imported = externalLook("effect", looks.celebration)?.duration;
    const ms = imported
      ? imported * 1000
      : DURATION_MS[shown.kind] + (gpuLook("effect", looks.celebration) ? 1200 : 0);
    const timer = window.setTimeout(() => setShown(queue.current.next()), ms);
    return () => window.clearTimeout(timer);
  }, [shown, announce, looks.celebration]);

  const value = useMemo(() => celebrate, [celebrate]);
  return (
    <CelebrationContext.Provider value={value}>
      {children}
      {shown ? <CelebrationLayer event={shown} reduced={reduced} /> : null}
    </CelebrationContext.Provider>
  );
}

function CelebrationLayer({ event, reduced }: { event: CelebrationEvent; reduced: boolean }) {
  const { looks } = useTheme();
  return <CelebrationScene effect={looks.celebration} event={event} reduced={reduced} />;
}

/**
 * One celebration as it plays (027) — the real one over the page, or ``contained`` in a box (the shop's
 * preview of an effect, scaled down to the box).
 */
export function CelebrationScene({
  effect,
  event,
  reduced = false,
  contained = false,
}: {
  effect: string;
  event: CelebrationEvent;
  reduced?: boolean;
  contained?: boolean;
}) {
  // issue 1 / 028: a pack's celebration (Portalab's own included) — its GPU scene or its own script
  const imported = externalLook("effect", effect);
  const drawn = useGpuLook("effect", effect);
  const gpu = drawn ? { effect: drawn.effect, from: drawn.start } : undefined;
  const spec = gpu
    ? { count: 0, layer: "badge" as const }
    : (EFFECTS[effect] ?? { count: 0, layer: "badge" as const });
  const count = Math.round((event.kind === "level" ? spec.count * 1.5 : spec.count) * (contained ? 0.6 : 1));
  const particles = Array.from({ length: count }, (_, i) => ({
    key: `${effect}-${i}`,
    style: {
      "--i": i,
      "--n": count,
      "--x": `${(seeded(i, 1) * 100).toFixed(1)}%`,
      "--d": `${(seeded(i, 2) * 0.6).toFixed(2)}s`,
      "--s": (0.7 + seeded(i, 3) * 0.8).toFixed(2),
      "--r": `${Math.round(seeded(i, 4) * 720 - 360)}deg`,
      "--h": Math.round(seeded(i, 5) * 360),
      "--cx": `${((i % GRID) - (GRID - 1) / 2) * 0.95}rem`,
      "--cy": `${(Math.floor(i / GRID) - 1.5) * 0.95}rem`,
    } as React.CSSProperties,
  }));
  const fx = particles.map((particle) => (
    <span key={particle.key} className="celebration-fx" style={particle.style}>
      {spec.icon ? <Icon name={spec.icon} size={22} /> : null}
    </span>
  ));
  return (
    <div
      className="ds-celebration"
      data-kind={event.kind}
      data-effect={effect}
      data-reduced={reduced ? "true" : undefined}
      data-contained={contained || undefined}
      aria-hidden="true"
    >
      {reduced || !count ? null : spec.layer === "screen" ? (
        <div className="celebration-screen">{fx}</div>
      ) : (
        <div className="ds-celebration__particles">{fx}</div>
      )}
      {gpu && !reduced ? (
        <FxLayer
          effect={gpu.effect}
          from={gpu.from}
          maxSide={contained ? 420 : 1100}
          className="celebration-gpu"
        />
      ) : null}
      {imported?.kind === "js" && !reduced ? (
        <ExternalScript
          element={imported}
          className="celebration-gpu"
          context={{ reducedMotion: reduced, text: event.text }}
        />
      ) : null}
      {effect === "lightning" && !reduced ? <span className="celebration-flash" /> : null}
      {effect === "portal" && !reduced ? <span className="celebration-portal" /> : null}
      <span className="ds-celebration__badge" data-text={event.text}>
        {event.text}
      </span>
    </div>
  );
}
