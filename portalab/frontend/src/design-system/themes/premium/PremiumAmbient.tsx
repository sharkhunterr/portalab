import { type ReactNode, useEffect, useRef, useState } from "react";

/**
 * #68: the premium ambiences — a GPU shader (fire, storm, sandstorm, polar lights, deep space, underwater,
 * downpour, digital rain) or particles (blizzard, fireworks, constellation mesh), drawn on a canvas loaded
 * only when chosen. Decorative (``aria-hidden``, no pointer events), paused while the tab is hidden; when
 * the device cannot draw it (no WebGL, an error), the CSS ambience given as ``fallback`` shows instead.
 */
export const SHADER_AMBIENTS = [
  "inferno",
  "thunderstorm",
  "sandstorm",
  "polar",
  "cosmos",
  "abyss",
  "downpour",
  "matrix",
] as const;
export const PARTICLE_AMBIENTS = ["blizzard", "fireworks", "mesh"] as const;
const SHADERS = new Set<string>(SHADER_AMBIENTS);

/** The CSS ambience standing in for each premium one. */
export const PREMIUM_FALLBACK: Record<string, string> = {
  inferno: "embers",
  thunderstorm: "rain",
  sandstorm: "sand",
  polar: "aurora",
  cosmos: "starfield",
  abyss: "bubbles",
  downpour: "rain",
  matrix: "code-rain",
  blizzard: "snow",
  fireworks: "sparkles",
  mesh: "fireflies",
};

export function isPremiumAmbient(kind: string): boolean {
  return kind in PREMIUM_FALLBACK;
}

// a page full of previews (the shop, the pickers) must not open more canvases than browsers allow
const MAX_RUNNING = 6;
let running = 0;
const freed = new EventTarget();
function take(): boolean {
  if (running >= MAX_RUNNING) return false;
  running += 1;
  return true;
}
function release() {
  running = Math.max(0, running - 1);
  freed.dispatchEvent(new Event("freed"));
}

export function PremiumAmbient({
  kind,
  contained,
  fallback,
}: {
  kind: string;
  contained: boolean;
  fallback: ReactNode;
}) {
  const host = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [failed, setFailed] = useState(false);
  const [visible, setVisible] = useState(!contained); // a preview runs only while on screen
  const [slot, setSlot] = useState(false);

  useEffect(() => {
    if (!contained || !host.current || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(([entry]) => setVisible(Boolean(entry?.isIntersecting)), {
      rootMargin: "120px",
    });
    observer.observe(host.current);
    return () => observer.disconnect();
  }, [contained]);

  const held = useRef(false);
  useEffect(() => {
    if (!visible) return;
    const claim = () => {
      if (!held.current && take()) {
        held.current = true;
        setSlot(true);
        freed.removeEventListener("freed", claim);
      }
    };
    claim();
    freed.addEventListener("freed", claim);
    return () => {
      freed.removeEventListener("freed", claim);
      if (held.current) {
        held.current = false;
        release();
      }
      setSlot(false);
    };
  }, [visible]);

  useEffect(() => {
    setFailed(false);
    if (!slot) return;
    let stop: (() => void) | null = null;
    let cancelled = false;
    (async () => {
      try {
        if (SHADERS.has(kind)) {
          const [{ runShader }, { SHADERS: sources }] = await Promise.all([
            import("./shaderRunner"),
            import("./shaders"),
          ]);
          const source = sources[kind];
          if (cancelled || !canvas.current || !source) return;
          stop = runShader(canvas.current, source);
        } else {
          const { runParticles } = await import("./particleRunner");
          if (cancelled || !host.current) return;
          stop = await runParticles(host.current, kind);
          if (cancelled) stop?.();
        }
        if (!stop && !cancelled) setFailed(true);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      stop?.();
    };
  }, [kind, slot]);

  if (failed) return <>{fallback}</>;
  return (
    <div
      data-waiting={!slot || undefined}
      ref={host}
      className="ambient ambient--premium"
      data-ambient={kind}
      data-contained={contained || undefined}
      aria-hidden="true"
    >
      {SHADERS.has(kind) ? <canvas ref={canvas} className="ambient__canvas" /> : null}
      {!slot ? fallback : null}
    </div>
  );
}
