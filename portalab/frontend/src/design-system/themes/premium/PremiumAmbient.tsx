import { type ReactNode, useEffect, useRef, useState } from "react";
import { liveAmbiences } from "../../motion/budget";

/**
 * #68: the premium ambiences — drawn by the GPU in layers: a shader (flames, clouds and rain, dust
 * billows, polar lights, deep space, underwater, digital rain), thousands of particles carried by a
 * turbulent flow (sand grains, snow, embers), a moving wireframe landscape, or tsParticles (fireworks,
 * a constellation). Loaded only when chosen; decorative (``aria-hidden``, no pointer events), paused while
 * the tab is hidden; when the device cannot draw it (no WebGL, an error) the CSS ``fallback`` shows.
 */
interface Layers {
  shader?: string;
  flow?: string | string[];
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
  volcano: { shader: "volcano", flow: ["ash", "embers"] },
  blackhole: { shader: "blackhole" },
  reef: { shader: "reef", flow: ["plankton", "school"] },
  firestorm: { shader: "firestorm", flow: "windash" },
  whiteout: { shader: "whiteout", flow: "nightsnow" },
  liquidmetal: { shader: "liquidmetal" },
  plasma: { shader: "plasma" },
  forest: { shader: "forest", flow: "fireflies" },
  neoncity: { shader: "neoncity" },
  haunted: { shader: "haunted", flow: "wisps" },
  darkness: { shader: "darkness" },
  lostsignal: { shader: "lostsignal" },
  garland: { shader: "garland", flow: "gentlesnow" },
  christmasnight: { shader: "christmasnight", flow: "gentlesnow" },
  hearth: { shader: "hearth", flow: "crackle" },
  goldenhour: { shader: "goldenhour", flow: "motes" },
  windowrain: { shader: "windowrain" },
  summerfield: { shader: "summerfield", flow: "butterflies" },
  soapbubbles: { shader: "soapbubbles" },
  skylanterns: { shader: "skylanterns" },
  autumnlane: { shader: "autumnlane", flow: "motes" },
  pixelcamp: { shader: "pixelcamp" },
  pixelbeach: { shader: "pixelbeach" },
  pixelballoons: { shader: "pixelballoons" },
  amberglow: { shader: "amberglow" },
  candlelight: { shader: "candlelight", flow: "motes" },
  steam: { shader: "steam" },
  fairybokeh: { shader: "fairybokeh" },
  warmsilk: { shader: "warmsilk" },
  honey: { shader: "honey" },
  knit: { shader: "knit" },
  paintmix: { shader: "paintmix" },
  acrylicpour: { shader: "acrylicpour" },
  watercolor: { shader: "watercolor" },
  marbling: { shader: "marbling" },
  poppaint: { shader: "poppaint" },
  poppour: { shader: "poppour" },
  popwatercolor: { shader: "popwatercolor" },
  popmarbling: { shader: "popmarbling" },
  lavalamp: { shader: "lavalamp" },
  impasto: { shader: "impasto" },
  paintribbon: { shader: "paintribbon" },
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
  volcano: "ash",
  blackhole: "starfield",
  reef: "bubbles",
  firestorm: "embers",
  whiteout: "snow",
  liquidmetal: "aurora",
  plasma: "aurora",
  forest: "fireflies",
  neoncity: "lights",
  haunted: "fog",
  darkness: "veins",
  lostsignal: "vhs",
  garland: "lights",
  christmasnight: "snow",
  hearth: "embers",
  goldenhour: "bokeh",
  windowrain: "rain",
  summerfield: "meadow",
  soapbubbles: "bubbles",
  skylanterns: "lanterns",
  autumnlane: "leaves",
  pixelcamp: "pixelsky",
  pixelbeach: "pixelsky",
  pixelballoons: "pixelsky",
  amberglow: "bokeh",
  candlelight: "embers",
  steam: "fog",
  fairybokeh: "bokeh",
  warmsilk: "aurora",
  honey: "aurora",
  knit: "bokeh",
  paintmix: "aurora",
  acrylicpour: "aurora",
  watercolor: "bokeh",
  marbling: "aurora",
  poppaint: "aurora",
  poppour: "aurora",
  popwatercolor: "bokeh",
  popmarbling: "aurora",
  lavalamp: "bubbles",
  impasto: "aurora",
  paintribbon: "aurora",
};

export function isPremiumAmbient(kind: string): boolean {
  return kind in LAYERS;
}

/** #68: whether this device draws the premium ambiences with its GPU, and which chip (when it says). */
let known: { webgl: boolean; gpu: string | null } | null = null;
export function webglInfo(): { webgl: boolean; gpu: string | null } {
  if (known) return known; // asked once: each test opens a GPU context of its own
  known = askWebgl();
  return known;
}
function askWebgl(): { webgl: boolean; gpu: string | null } {
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

// a page full of previews (the shop, the pickers) must not open more canvases than browsers allow — phones
// give far fewer GPU contexts and less memory (the budget counts them: ``liveAmbiences``)
let running = 0;
const freed = new EventTarget();
/** #29: as many previews at once as the motion budget allows (none when still: the CSS one, paused). */
function take(): boolean {
  if (running >= liveAmbiences()) return false;
  running += 1;
  return true;
}
function release() {
  running = Math.max(0, running - 1);
  freed.dispatchEvent(new Event("freed"));
}

function flows(layers: Layers): string[] {
  return layers.flow === undefined ? [] : Array.isArray(layers.flow) ? layers.flow : [layers.flow];
}

async function start(layers: Layers, canvases: HTMLCanvasElement[], host: HTMLElement) {
  const stops: Array<() => void> = [];
  const stopAll = () => {
    for (const stop of stops) stop();
  };
  let index = 0;
  const next = () => canvases[index++] as HTMLCanvasElement;
  if (layers.shader) {
    const [{ runShader }, { SHADERS }, { COZY_SHADERS }, { WARM_SHADERS }] = await Promise.all([
      import("./shaderRunner"),
      import("./shaders"),
      import("./cozyShaders"),
      import("./warmShaders"),
    ]);
    const source = SHADERS[layers.shader] ?? COZY_SHADERS[layers.shader] ?? WARM_SHADERS[layers.shader];
    const stop = runShader(next(), source as string);
    if (!stop) return null;
    stops.push(stop);
  }
  if (layers.mesh) {
    const { runMesh } = await import("./meshRunner");
    const stop = runMesh(next());
    if (!stop) return stopAll(), null;
    stops.push(stop);
  }
  for (const name of flows(layers)) {
    const { FLOWS, runFlow } = await import("./flowRunner");
    const preset = FLOWS[name];
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
  const canvasCount = [layers.shader, layers.mesh].filter(Boolean).length + flows(layers).length;
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

  // the GPU took the context back (memory, too many contexts): the CSS ambience instead, never a frozen
  // or black layer
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const lost = (event: Event) => {
      event.preventDefault();
      setFailed(true);
    };
    element.addEventListener("webglcontextlost", lost, true);
    return () => element.removeEventListener("webglcontextlost", lost, true);
  }, []);

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
