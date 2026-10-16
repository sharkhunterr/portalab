import { type ReactNode, useEffect, useRef, useState } from "react";
import { liveAmbiences } from "../../motion/budget";
import { externalFx, externalLook, fxName } from "../../visuals/registry";
import type { Uniforms } from "./shaderRunner";

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
  /** its shader is written after the noise safe on phones of lower precision */
  safe?: boolean;
}

// 028 (B2): the premium ambiences are their packs' (Portalab's own included) — each element holds its shader
// and its layers (``render.params``: flows, particles, a landscape, the CSS ambience standing in); what stays
// here is « live weather », drawn from the weather report's numbers
const WEATHER_SKY: Layers = { shader: "weathersky" };

function packLayers(kind: string): Layers | undefined {
  const element = externalLook("ambient", kind) ?? externalLook("profile_background", kind);
  if (!element) return undefined;
  const params = element.params ?? {};
  const flow = Array.isArray(params.flow)
    ? params.flow.filter((f): f is string => typeof f === "string")
    : [];
  const layers: Layers = {
    ...(flow.length ? { flow } : {}),
    ...(typeof params.particles === "string" ? { particles: params.particles } : {}),
    ...(params.mesh === true ? { mesh: true } : {}),
  };
  if (element.kind === "glsl") return { shader: fxName(element), ...layers, safe: params.common === "safe" };
  if (element.kind === "renderer" && element.renderer === "layers" && Object.keys(layers).length)
    return layers;
  return undefined;
}

function layersOf(kind: string): Layers | undefined {
  return kind === "weathersky" ? WEATHER_SKY : packLayers(kind);
}

export function isPremiumAmbient(kind: string): boolean {
  return layersOf(kind) !== undefined;
}

/** The CSS ambience standing in for a premium one (its pack says which). */
export function premiumFallback(kind: string): string {
  if (kind === "weathersky") return "skyclouds";
  const element = externalLook("ambient", kind) ?? externalLook("profile_background", kind);
  const fallback = element?.params?.fallback;
  return typeof fallback === "string" ? fallback : "none";
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

async function start(layers: Layers, canvases: HTMLCanvasElement[], host: HTMLElement, uniforms?: Uniforms) {
  const stops: Array<() => void> = [];
  const stopAll = () => {
    for (const stop of stops) stop();
  };
  let index = 0;
  const next = () => canvases[index++] as HTMLCanvasElement;
  if (layers.shader) {
    const [{ runShader }, { COMMON }, { SAFE_COMMON, WEATHER }] = await Promise.all([
      import("./shaderRunner"),
      import("./shaders"),
      import("./weatherShader"),
    ]);
    const imported = externalFx(layers.shader);
    const source = imported
      ? `${layers.safe ? SAFE_COMMON : COMMON}${imported.body}`
      : layers.shader === "weathersky"
        ? WEATHER
        : null;
    if (!source) return null;
    const stop = runShader(next(), source as string, uniforms, Boolean(imported));
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
  uniforms,
}: {
  kind: string;
  contained: boolean;
  fallback: ReactNode;
  /** #88: the scene's numbers, asked each frame (a stable function) */
  uniforms?: Uniforms;
}) {
  const layers = layersOf(kind) ?? {};
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
        const started = await start(layers, canvases.current, host.current as HTMLElement, uniforms);
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
