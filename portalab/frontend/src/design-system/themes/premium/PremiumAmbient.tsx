import { type ReactNode, useEffect, useRef, useState } from "react";

/**
 * #68: the premium ambiences — drawn by the GPU in layers: a shader (flames, clouds and rain, dust
 * billows, polar lights, deep space, underwater, digital rain), thousands of particles carried by a
 * turbulent flow (sand grains, snow, embers), a moving wireframe landscape, or tsParticles (fireworks,
 * a constellation). Loaded only when chosen; decorative (``aria-hidden``, no pointer events), paused while
 * the tab is hidden; when the device cannot draw it (no WebGL, an error) the CSS ``fallback`` shows.
 */
interface Layers {
  shader?: string;
  flow?: string;
  particles?: string;
  mesh?: boolean;
}

const LAYERS: Record<string, Layers> = {
  inferno: { shader: "inferno", flow: "embers" },
  thunderstorm: { shader: "thunderstorm", flow: "storm" },
  sandstorm: { shader: "sandstorm", flow: "sand" },
  polar: { shader: "polar" },
  cosmos: { shader: "cosmos" },
  abyss: { shader: "abyss" },
  downpour: { shader: "downpour" },
  matrix: { shader: "matrix" },
  blizzard: { flow: "snow" },
  fireworks: { particles: "fireworks" },
  mesh: { particles: "mesh" },
  meshwave: { mesh: true },
};

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
  meshwave: "starfield",
};

export function isPremiumAmbient(kind: string): boolean {
  return kind in LAYERS;
}

/** #68: whether this device draws the premium ambiences with its GPU, and which chip (when it says). */
export function webglInfo(): { webgl: boolean; gpu: string | null } {
  try {
    const gl = document.createElement("canvas").getContext("webgl");
    if (!gl) return { webgl: false, gpu: null };
    const debug = gl.getExtension("WEBGL_debug_renderer_info");
    const gpu = debug ? String(gl.getParameter(debug.UNMASKED_RENDERER_WEBGL)) : null;
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return { webgl: true, gpu };
  } catch {
    return { webgl: false, gpu: null };
  }
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

async function start(layers: Layers, canvases: HTMLCanvasElement[], host: HTMLElement) {
  const stops: Array<() => void> = [];
  const stopAll = () => {
    for (const stop of stops) stop();
  };
  let index = 0;
  const next = () => canvases[index++] as HTMLCanvasElement;
  if (layers.shader) {
    const [{ runShader }, { SHADERS }] = await Promise.all([import("./shaderRunner"), import("./shaders")]);
    const stop = runShader(next(), SHADERS[layers.shader] as string);
    if (!stop) return null;
    stops.push(stop);
  }
  if (layers.mesh) {
    const { runMesh } = await import("./meshRunner");
    const stop = runMesh(next());
    if (!stop) return stopAll(), null;
    stops.push(stop);
  }
  if (layers.flow) {
    const { FLOWS, runFlow } = await import("./flowRunner");
    const preset = FLOWS[layers.flow];
    const stop = preset ? runFlow(next(), preset) : null;
    if (!stop) return stopAll(), null;
    stops.push(stop);
  }
  if (layers.particles) {
    const { runParticles } = await import("./particleRunner");
    const stop = await runParticles(host, layers.particles);
    if (!stop) return stopAll(), null;
    stops.push(stop);
  }
  return stopAll;
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
  const layers = LAYERS[kind] ?? {};
  const canvasCount = [layers.shader, layers.mesh, layers.flow].filter(Boolean).length;
  const host = useRef<HTMLDivElement>(null);
  const canvases = useRef<HTMLCanvasElement[]>([]);
  const [failed, setFailed] = useState(false);
  const [visible, setVisible] = useState(!contained); // a preview runs only while on screen
  const [slot, setSlot] = useState(false);
  const held = useRef(false);

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

  // biome-ignore lint/correctness/useExhaustiveDependencies: the layers follow the kind
  useEffect(() => {
    setFailed(false);
    if (!slot || !host.current) return;
    let stop: (() => void) | null = null;
    let cancelled = false;
    (async () => {
      try {
        const started = await start(layers, canvases.current, host.current as HTMLElement);
        if (cancelled) started?.();
        else if (started) stop = started;
        else setFailed(true);
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
      ref={host}
      className="ambient ambient--premium"
      data-ambient={kind}
      data-waiting={!slot || undefined}
      data-contained={contained || undefined}
      aria-hidden="true"
    >
      {Array.from({ length: canvasCount }, (_, i) => (
        <canvas
          // biome-ignore lint/suspicious/noArrayIndexKey: the layers of one ambience, in a fixed order
          key={i}
          ref={(element) => {
            if (element) canvases.current[i] = element;
          }}
          className="ambient__canvas"
        />
      ))}
      {!slot ? fallback : null}
    </div>
  );
}
