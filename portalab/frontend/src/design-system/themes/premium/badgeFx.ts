/**
 * #73, #77, #78: looks drawn by the GPU — living flames wrapped around a shape, electricity crackling over
 * it, water sloshing inside, magma under a cracked crust, ice, a spiral galaxy, liquid gold, toxic acid —
 * for level badges, notifications, titles, badges and avatar frames (any rounded shape: its corners are
 * read from the element), and full-stage level-up moments (supernova, phoenix, lightning strike, tidal
 * wave). One WebGL context for the whole page (browsers allow few): each visible look is drawn in turn
 * into it and copied onto its element's own small 2D canvas. 30 frames a second at most, nothing while the
 * tab is hidden or the element off screen, a still frame when motion is reduced. #29: a budget of looks
 * moving at once (the others hold a still frame until pointed at), halved with the frame rate when the
 * member chose discreet animations or the device saves energy; their positions measured twice a second. ``attachFx`` returns
 * ``null`` when the device cannot draw it (the element then keeps its CSS look).
 */

import { frameInterval, liveLooks, motionBudget, stillFor } from "../../motion/budget";
import { externalFx } from "../../visuals/registry";

export const FX_EFFECTS = [
  // a stage's backdrop: drifting banks of fog under moving projectors (the booster opening)
  "mist",
  // a legendary card's moment on that stage
  "radiance",
] as const;
export type FxBadge = (typeof FX_EFFECTS)[number];
const FULL_STAGE = new Set<string>(["mist", "radiance"]);

// high precision where the device has it: in medium precision (many phones by default) fast-moving noise
// stops moving once the time grows — the flames and the arcs looked frozen
const HEAD = `
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif
uniform vec2 u_res;
uniform float u_time;
uniform vec4 u_box; // the shape in the canvas: centre x, y and half width, height (pixels)
uniform float u_round; // its corner radius, in half heights (1: a pill, or a circle when square)
uniform float u_calm; // 1: text is written over it — its inside is kept dark enough to read;
// 2: an aura — nothing is drawn inside the shape (a name keeps its own letters)
uniform float u_cycle; // 1: a looks that comes and goes over and over (the time portal as a teleporter)
uniform float u_burst; // 1: a burst — it flares as the element appears and again as it leaves, then fades
uniform float u_age; // seconds since it appeared (the level-up moments' timeline)
uniform float u_hue; // a colour variant: the hue turned by this angle (a blue flame, a green bolt…)
uniform float u_shape; // 0 rounded box, 1 hexagon, 2 diamond, 3 shield, 4 star, 5 triangle (frames);
// 6 pointed ends, 7 slanted, 8 wavy edges (wide shapes: notifications)
uniform float u_close; // seconds since it started to leave (-1 while it stays): portals close
// an equilateral triangle, point up, of half side r (Inigo Quilez's distance)
float sdTri(vec2 p, float r) {
  float k = 1.7320508;
  p.x = abs(p.x) - r;
  p.y = p.y + r / k;
  if (p.x + k * p.y > 0.0) p = vec2(p.x - k * p.y, -k * p.x - p.y) / 2.0;
  p.x -= clamp(p.x, -2.0 * r, 0.0);
  return -length(p) * sign(p.y);
}
// the time vortex seen through a portal: rings like a clock face, a spiral turning in, sparks drawn in
vec3 vortex(vec2 c, float t) {
  float r = length(c) + 0.001;
  float a = atan(c.y, c.x);
  float spiral = sin(a * 3.0 + log(r) * 6.0 + t * 3.0);
  vec3 col = mix(vec3(0.02, 0.05, 0.2), vec3(0.15, 0.45, 1.0), smoothstep(-0.3, 1.0, spiral) * smoothstep(1.6, 0.1, r));
  col += vec3(1.0, 0.8, 0.35) * smoothstep(0.85, 1.0, spiral) * smoothstep(1.4, 0.2, r) * 0.6;
  float ring = fract(r * 2.5 - t * 0.6);
  col += vec3(0.6, 0.85, 1.0) * smoothstep(0.06, 0.0, abs(ring - 0.5)) * 0.35 * smoothstep(1.5, 0.3, r);
  float tick = step(0.94, fract(a / 6.2832 * 12.0 + t * 0.05)) * smoothstep(0.03, 0.0, abs(r - 0.8));
  col += vec3(1.0, 0.9, 0.6) * tick;
  col += vec3(1.0, 0.95, 0.85) * exp(-r * 7.0);
  return col;
}
float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 4; i++) {
    v += a * noise(p);
    p = mat2(0.8, 0.6, -0.6, 0.8) * p * 2.03 + 1.7;
    a *= 0.5;
  }
  return v;
}
// the shape: p in units of its half height; < 0 inside (a rounded box, or a frame's own outline)
float badge(vec2 p, float ax) {
  if (u_shape > 7.5) {
    // wavy edges (wide shapes: notifications)
    vec2 q = abs(p) - vec2(ax, 1.0) + 0.3;
    float b = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - 0.3;
    return b - 0.09 * sin(p.x * 5.0 + u_time * 1.5) * smoothstep(0.5, 1.0, abs(p.y));
  }
  if (u_shape > 6.5) {
    // slanted, like a parallelogram
    vec2 r = vec2(p.x + p.y * 0.35, p.y);
    vec2 q = abs(r) - vec2(ax - 0.35, 1.0) + 0.15;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - 0.15;
  }
  if (u_shape > 5.5) return max(abs(p.y) - 1.0, (abs(p.x) + abs(p.y) * 0.6 - ax) * 0.86); // pointed ends
  if (u_shape > 4.5) return sdTri(p - vec2(0.0, -0.12), min(ax, 1.0) * 1.12);
  if (u_shape > 3.5) {
    float a = atan(p.x, p.y);
    float r = 0.55 + 0.45 * pow(0.5 + 0.5 * cos(a * 5.0), 1.6);
    return (length(p) - r * min(ax, 1.0)) * 0.8;
  }
  if (u_shape > 2.5) {
    float w = 0.9 * min(ax, 1.0) * sqrt(clamp((p.y + 1.0) / 1.25, 0.0, 1.0));
    return max(max(abs(p.x) - w, p.y - 0.95), -1.0 - p.y);
  }
  if (u_shape > 1.5) return (abs(p.x) / min(ax, 1.0) + abs(p.y) - 1.0) * 0.7071;
  if (u_shape > 0.5) {
    vec3 k = vec3(-0.866025404, 0.5, 0.577350269);
    float r = min(1.0, ax * 0.866);
    vec2 q = abs(p.yx);
    q -= 2.0 * min(dot(k.xy, q), 0.0) * k.xy;
    q -= vec2(clamp(q.x, -k.z * r, k.z * r), r);
    return length(q) * sign(q.y);
  }
  vec2 q = abs(p) - vec2(ax, 1.0) + u_round;
  return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - u_round;
}
vec4 over(vec4 under, vec3 c, float a) {
  a = clamp(a, 0.0, 1.0);
  return vec4(c * a + under.rgb * (1.0 - a), a + under.a * (1.0 - a));
}
`;

const MAIN_OPEN = `
void main() {
  vec2 p = (gl_FragCoord.xy - u_box.xy) / u_box.w;
  float ax = u_box.z / u_box.w;
  float d = badge(p, ax);
  float t = u_time;
  vec4 o = vec4(0.0);
`;

// 028: the looks' effects are their packs' (each element holds its fragment); what stays is Portalab's own
// booster stage — its fog and a legendary card's moment, drawn by the default scene
const EFFECTS: Record<FxBadge, string> = {
  // mist: banks of fog drifting slowly over the floor, warped on themselves, and projectors hung above the
  // stage, each sweeping on its own — their light only shows where it goes through the haze
  mist: `
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float aspect = u_res.x / u_res.y;
  float tm = u_time * 0.05;
  vec2 q = c * 1.7;
  vec2 warp = vec2(fbm(q + vec2(tm, -tm * 0.6)), fbm(q * 1.3 + vec2(-tm * 0.8, tm) + 3.1));
  float fog = fbm(q * 1.15 + warp * 1.8 + vec2(tm * 1.6, tm * 0.3));
  float low = smoothstep(0.3, -0.5, c.y);
  float dens = smoothstep(0.22, 0.8, fog) * (0.35 + 0.65 * low);
  vec3 dark = mix(vec3(0.16, 0.11, 0.34), vec3(0.1, 0.17, 0.38), smoothstep(-0.6, 0.6, c.x + warp.x - 0.5));
  o = over(o, dark, dens * 0.72);
  float light = 0.0;
  vec3 tint = vec3(0.0);
  float span = min(aspect, 1.9) * 0.46;
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float x = (fi / 3.0 - 0.5) * 2.0 * span;
    vec2 v = c - vec2(x, 0.6);
    // aimed below, leaning towards the middle, swinging slowly — never two in step
    float aim = sin(u_time * (0.16 + 0.05 * fi) + fi * 2.1) * 0.42 - x * 0.45;
    float off = atan(v.x, -v.y) - aim;
    float width = 0.075 + 0.025 * sin(u_time * 0.23 + fi * 1.3);
    float cone = smoothstep(width, width * 0.15, abs(off)) * smoothstep(1.7, 0.15, length(v)) * step(v.y, 0.0);
    cone *= 0.75 + 0.25 * sin(u_time * (0.4 + 0.1 * fi) + fi * 4.0);
    vec3 col = mix(vec3(0.74, 0.66, 1.0), vec3(0.62, 0.8, 1.0), mod(fi, 2.0));
    light += cone;
    tint += col * cone;
  }
  vec3 beam = tint / max(light, 0.001);
  o = over(o, beam, min(light, 1.0) * (0.06 + 0.55 * dens + 0.25 * fbm(q * 2.4 - warp + tm * 3.0) * min(light, 1.0)));
  float wisp = smoothstep(0.62, 0.8, fbm(q * 3.0 - warp * 2.0 + vec2(-tm * 2.5, tm)));
  o = over(o, vec3(0.78, 0.74, 0.98), wisp * (0.06 + 0.3 * min(light, 1.0)) * (0.4 + 0.6 * low));
`,
  // radiance: a legendary's moment — the dark closes in, golden motes are drawn in a spiral to the middle
  // while a halo swells; at the turn a flash, two rings of light and soft rays breathing out, embers rising
  // and slow bokeh — then it all fades away (timed from when it starts: the turn comes at 2.1 s)
  radiance: `
  // sized on the screen's narrow side: on a phone held upright the halo stays round the card
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / min(u_res.x, u_res.y) - vec2(0.0, 0.05);
  float a = u_age;
  float r = length(c);
  float ang = atan(c.y, c.x);
  float hit = a - 2.1;
  float after = step(0.0, hit);
  float fade = 1.0 - smoothstep(3.0, 3.75, a);
  vec3 gold = vec3(1.0, 0.72, 0.28);
  vec3 pale = vec3(1.0, 0.94, 0.78);
  o = over(o, vec3(0.03, 0.015, 0.0), 0.55 * smoothstep(0.0, 0.9, a) * fade * smoothstep(0.15, 0.8, r));
  float swell = smoothstep(0.0, 2.1, a);
  float halo = exp(-r * r * mix(40.0, 9.0, swell * swell)) * (0.25 + 0.75 * swell);
  halo = mix(halo, exp(-r * r * 7.0) * 0.6, after * smoothstep(0.0, 0.3, hit));
  o = over(o, gold, halo * 0.7 * fade);
  float soft = 0.5 + 0.5 * sin(ang * 7.0 + sin(ang * 3.0 + a * 0.5) * 2.0 + a * 0.35);
  soft *= 0.5 + 0.5 * sin(ang * 11.0 - a * 0.6 + 1.3);
  float rays = pow(soft, 2.5) * exp(-r * 1.7) * mix(0.15 * swell * swell, 0.9, after * smoothstep(0.0, 0.25, hit));
  o = over(o, mix(gold, pale, 0.4), rays * 0.6 * fade);
  for (int i = 0; i < 28; i++) {
    float fi = float(i);
    float life = fract(a * (0.45 + 0.2 * hash(vec2(fi, 11.0))) + hash(vec2(fi, 12.0)));
    float th = hash(vec2(fi, 13.0)) * 6.2832 + life * 2.5;
    vec2 pos = vec2(cos(th), sin(th)) * mix(1.0, 0.04, life * life);
    float m = smoothstep(0.012, 0.0, length(c - pos)) * smoothstep(0.0, 0.2, life) * (1.0 - after);
    o = over(o, pale, m * swell);
  }
  o = over(o, vec3(1.0, 0.98, 0.92), after * exp(-hit * 6.0) * exp(-r * 2.6) * fade);
  float ring1 = smoothstep(0.035, 0.0, abs(r - hit * 1.5)) * exp(-hit * 1.6);
  float ring2 = smoothstep(0.02, 0.0, abs(r - (hit - 0.15) * 1.1)) * exp(-hit * 2.0) * step(0.15, hit);
  o = over(o, pale, (ring1 * 0.75 + ring2 * 0.5) * after * fade);
  for (int i = 0; i < 40; i++) {
    float fi = float(i);
    float dir = hash(vec2(fi, 21.0)) * 6.2832;
    float speed = 0.25 + 0.6 * hash(vec2(fi, 22.0));
    float h = max(hit, 0.0);
    vec2 pos = vec2(cos(dir), sin(dir)) * speed * (1.0 - exp(-h * 2.2)) * 0.9 + vec2(sin(h * 2.0 + fi) * 0.03, h * 0.12);
    float flick = 0.6 + 0.4 * sin(a * 18.0 + fi * 3.0);
    float e = smoothstep(0.009, 0.0, length(c - pos)) * flick * smoothstep(1.4, 0.3, h);
    o = over(o, mix(gold, pale, hash(vec2(fi, 23.0))), e * after * fade);
  }
  for (int i = 0; i < 9; i++) {
    float fi = float(i);
    vec2 pos = vec2((hash(vec2(fi, 31.0)) - 0.5) * 1.6, (hash(vec2(fi, 32.0)) - 0.5) * 0.9 + a * 0.03);
    float b = smoothstep(0.07, 0.02, length(c - pos));
    o = over(o, vec3(1.0, 0.86, 0.58), b * 0.1 * swell * fade);
  }
`,
};

// faded towards the canvas' edges: never a cut flame or a visible rectangle around the badge
const CLOSE = `
  if (abs(u_hue) > 0.001) {
    vec3 k3 = vec3(0.57735);
    o.rgb = o.rgb * cos(u_hue) + cross(k3, o.rgb) * sin(u_hue) + k3 * dot(k3, o.rgb) * (1.0 - cos(u_hue));
  }
  o.rgb *= 1.0 - 0.5 * min(u_calm, 1.0) * smoothstep(0.05, -0.1, d);
  if (u_calm > 1.5) {
    // an aura: only its light, fading in softly from inside the shape — a sharp edge there would draw a
    // frame (a box) round the name instead of a halo; its dark parts would draw a black plate
    o *= smoothstep(-0.45, 0.4, d) * (0.55 + 0.45 * smoothstep(0.0, 0.5, d));
    o.a = min(o.a, max(o.r, max(o.g, o.b)) * 1.4);
  }
  if (u_burst > 0.5) {
    float flare = 1.0 - smoothstep(0.4, 1.9, u_age);
    float leave = u_close < 0.0 ? 0.0 : smoothstep(0.0, 0.12, u_close) * (1.0 - smoothstep(1.0, 1.4, u_close));
    o *= clamp(max(flare, leave), 0.0, 1.0);
  }
  float edge = min(min(gl_FragCoord.x, u_res.x - gl_FragCoord.x), min(gl_FragCoord.y, u_res.y - gl_FragCoord.y));
  // an aura (a name) fades out well before its canvas' edges: never the outline of a box
  gl_FragColor = o * smoothstep(0.0, u_box.w * (u_calm > 1.5 ? 1.8 : 0.7), edge);
}`;
const CLOSE_FULL = `
  gl_FragColor = o;
}`;

const VERTEX = `attribute vec2 a_pos;
void main() { gl_Position = vec4(a_pos, 0.0, 1.0); }`;

interface Program {
  program: WebGLProgram;
  res: WebGLUniformLocation | null;
  time: WebGLUniformLocation | null;
  box: WebGLUniformLocation | null;
  round: WebGLUniformLocation | null;
  calm: WebGLUniformLocation | null;
  burst: WebGLUniformLocation | null;
  cycle: WebGLUniformLocation | null;
  age: WebGLUniformLocation | null;
  shape: WebGLUniformLocation | null;
  hue: WebGLUniformLocation | null;
  close: WebGLUniformLocation | null;
}

export interface FxOptions {
  /** text is written over it: its inside is kept dark enough to read */
  calm?: boolean;
  /** an aura: nothing drawn inside the shape (names keep their letters) */
  aura?: boolean;
  /** comes and goes over and over (the time portal as a teleporter) */
  cycle?: boolean;
  /** a burst that keeps its own timeline (open, bring in, take out, close): the time portal */
  portal?: boolean;
  /** seconds into its timeline it starts at (a short celebration skips the slow build-up) */
  from?: number;
  /** largest side of its canvas in pixels (a full stage needs more than a badge) */
  maxSide?: number;
  /** its outline: 0 rounded box (the element's corners), 1 hexagon, 2 diamond, 3 shield, 4 star */
  shape?: number;
  /** a colour variant: hue turned by this angle in radians */
  hue?: number;
}

interface Instance {
  canvas: HTMLCanvasElement;
  host: HTMLElement;
  effect: string;
  context: CanvasRenderingContext2D;
  visible: boolean;
  drawn: boolean;
  seed: number;
  born: number;
  options: FxOptions;
  /** when its element started to leave (``data-leaving``): portals close */
  closing?: number;
  /** #29: pointed at or focused — it moves even beyond the budget */
  hovered: boolean;
  /** #29: where it sits, measured at most every half second (not every frame) */
  geometry?: Geometry | undefined;
}

interface Geometry {
  at: number;
  w: number;
  h: number;
  scale: number;
  cx: number;
  cy: number;
  halfWidth: number;
  halfHeight: number;
  round: number;
}

const GEOMETRY_MS = 500;
const MAX_SIDE = 512; // pixels of a badge's canvas, at most
let gl: WebGLRenderingContext | null = null;
let shared: HTMLCanvasElement | null = null;
let broken = false;
const programs = new Map<string, Program | null>();
const instances = new Set<Instance>();
let frame = 0;
let last = 0;
const started = typeof performance === "undefined" ? 0 : performance.now();
let observer: IntersectionObserver | null = null;

function setup(): WebGLRenderingContext | null {
  if (gl || broken) return gl;
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  shared = canvas;
  try {
    gl = canvas.getContext("webgl", {
      alpha: true,
      premultipliedAlpha: true,
      antialias: false,
      depth: false,
    });
  } catch {
    gl = null;
  }
  if (!gl) {
    broken = true;
    return null;
  }
  canvas.addEventListener("webglcontextlost", (event) => {
    event.preventDefault();
    broken = true;
    gl = null;
    for (const instance of instances) instance.host.dataset.fxFailed = "true";
  });
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  return gl;
}

/** « burst:blaze » plays the flames of « blaze » as a burst (a notification's entrance and exit) */
function baseOf(effect: string): string {
  return effect.startsWith("burst:") ? effect.slice(6) : effect;
}

/** The fragment shader an effect is drawn with (also read by tests and previews). */
export function fxFragment(effect: string): string {
  const base = baseOf(effect);
  // issue 1: an imported pack's look, in the same frame as the built-in ones
  const external = externalFx(base);
  const body = external ? external.body : (EFFECTS as Record<string, string>)[base];
  return `${HEAD}${MAIN_OPEN}${body}${stageOf(base) ? CLOSE_FULL : CLOSE}`;
}

function stageOf(effect: string): boolean {
  return FULL_STAGE.has(effect) || Boolean(externalFx(effect)?.stage);
}

function compile(context: WebGLRenderingContext, effect: string): Program | null {
  if (programs.has(effect)) return programs.get(effect) ?? null;
  const make = (type: number, source: string) => {
    const shader = context.createShader(type);
    if (!shader) return null;
    context.shaderSource(shader, source);
    context.compileShader(shader);
    if (!context.getShaderParameter(shader, context.COMPILE_STATUS)) {
      console.warn("badge shader:", context.getShaderInfoLog(shader));
      return null;
    }
    return shader;
  };
  const vertex = make(context.VERTEX_SHADER, VERTEX);
  const fragment = make(context.FRAGMENT_SHADER, fxFragment(effect));
  const program = context.createProgram();
  let made: Program | null = null;
  if (vertex && fragment && program) {
    context.attachShader(program, vertex);
    context.attachShader(program, fragment);
    context.linkProgram(program);
    if (context.getProgramParameter(program, context.LINK_STATUS)) {
      made = {
        program,
        res: context.getUniformLocation(program, "u_res"),
        time: context.getUniformLocation(program, "u_time"),
        box: context.getUniformLocation(program, "u_box"),
        round: context.getUniformLocation(program, "u_round"),
        calm: context.getUniformLocation(program, "u_calm"),
        burst: context.getUniformLocation(program, "u_burst"),
        cycle: context.getUniformLocation(program, "u_cycle"),
        age: context.getUniformLocation(program, "u_age"),
        shape: context.getUniformLocation(program, "u_shape"),
        hue: context.getUniformLocation(program, "u_hue"),
        close: context.getUniformLocation(program, "u_close"),
      };
    }
  }
  programs.set(effect, made);
  return made;
}

function reducedMotion(): boolean {
  return (
    document.documentElement.dataset.reducedMotion === "true" ||
    Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches)
  );
}

function measure(instance: Instance, now: number): Geometry | null {
  const known = instance.geometry;
  if (known && now - known.at < GEOMETRY_MS) return known;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const area = instance.canvas.getBoundingClientRect();
  const pill = instance.host.getBoundingClientRect();
  if (!area.width || !area.height) return null;
  const scale = Math.min(dpr, (instance.options.maxSide ?? MAX_SIDE) / Math.max(area.width, area.height));
  const halfHeight = (pill.height / 2) * scale;
  const corner = Number.parseFloat(getComputedStyle(instance.host).borderTopLeftRadius) || 0;
  instance.geometry = {
    at: now,
    w: Math.max(1, Math.round(area.width * scale)),
    h: Math.max(1, Math.round(area.height * scale)),
    scale,
    // the badge's rectangle in the canvas, y from the bottom (GL)
    cx: (pill.left + pill.width / 2 - area.left) * scale,
    cy: (area.bottom - (pill.top + pill.height / 2)) * scale,
    halfWidth: (pill.width / 2) * scale,
    halfHeight,
    round: Math.min(1, (corner * scale) / Math.max(halfHeight, 1)),
  };
  return instance.geometry;
}

function draw(context: WebGLRenderingContext, instance: Instance, time: number): boolean {
  const program = compile(context, instance.effect);
  if (!program || !shared) return false;
  const geometry = measure(instance, performance.now());
  if (!geometry) return true;
  const { w, h } = geometry;
  if (shared.width < w || shared.height < h) {
    shared.width = Math.max(shared.width, w);
    shared.height = Math.max(shared.height, h);
  }
  if (instance.canvas.width !== w || instance.canvas.height !== h) {
    instance.canvas.width = w;
    instance.canvas.height = h;
  }
  context.viewport(0, 0, w, h);
  context.clearColor(0, 0, 0, 0);
  context.clear(context.COLOR_BUFFER_BIT);
  // biome-ignore lint/correctness/useHookAtTopLevel: WebGL's useProgram, not a React hook
  context.useProgram(program.program);
  const position = context.getAttribLocation(program.program, "a_pos");
  context.enableVertexAttribArray(position);
  context.vertexAttribPointer(position, 2, context.FLOAT, false, 0, 0);
  context.uniform2f(program.res, w, h);
  context.uniform1f(program.time, time + instance.seed);
  context.uniform4f(program.box, geometry.cx, geometry.cy, geometry.halfWidth, geometry.halfHeight);
  context.uniform1f(program.round, geometry.round);
  context.uniform1f(program.calm, instance.options.aura ? 2 : instance.options.calm ? 1 : 0);
  // the time portal keeps its own timeline (open, bring in, take out, close) rather than a mere burst
  const burst = instance.effect.startsWith("burst:") && !instance.options.portal;
  context.uniform1f(program.burst, burst ? 1 : 0);
  context.uniform1f(program.cycle, instance.options.cycle ? 1 : 0);
  context.uniform1f(program.shape, instance.options.shape ?? 0);
  context.uniform1f(program.hue, instance.options.hue ?? 0);
  if (instance.host.dataset.leaving !== undefined && instance.closing === undefined)
    instance.closing = performance.now();
  context.uniform1f(
    program.close,
    instance.closing === undefined ? -1 : (performance.now() - instance.closing) / 1000,
  );
  context.uniform1f(program.age, still() ? 2.5 : (performance.now() - instance.born) / 1000);
  context.drawArrays(context.TRIANGLES, 0, 3);
  instance.context.clearRect(0, 0, w, h);
  instance.context.drawImage(shared, 0, shared.height - h, w, h, 0, 0, w, h);
  return true;
}

/** #29: a moment that plays once (a notification's burst, a level-up, a celebration) always plays. */
function timed(instance: Instance): boolean {
  return instance.effect.startsWith("burst:") || stageOf(instance.effect);
}

/** #29: the looks that move this frame — the timed ones, those pointed at, then the largest, up to the
 * budget; the others hold the still frame they were last drawn with until they are pointed at. */
function moving(visible: Instance[], limit: number): Set<Instance> {
  if (visible.length <= limit) return new Set(visible);
  const rank = (instance: Instance) =>
    timed(instance) ? 3 : instance.hovered ? 2 : instance.options.cycle ? 1 : 0;
  const area = (instance: Instance) => (instance.geometry ? instance.geometry.w * instance.geometry.h : 0);
  const ordered = [...visible].sort((a, b) => rank(b) - rank(a) || area(b) - area(a));
  const live = new Set(ordered.slice(0, limit));
  for (const instance of ordered) if (rank(instance) >= 2) live.add(instance);
  return live;
}

/** issue 1: an imported pack's look that keeps the device behind (a frame far too long to draw, again and
 * again) is given up — its element keeps its CSS look; every element drawn by it stops. */
const strikes = new Map<string, number>();
const GIVEN_UP = new Set<string>();
const SLOW_MS = 120;
function watch(instance: Instance, spent: number) {
  const effect = baseOf(instance.effect);
  if (spent < SLOW_MS) return;
  const count = (strikes.get(effect) ?? 0) + 1;
  strikes.set(effect, count);
  if (count < 3) return;
  GIVEN_UP.add(effect);
  console.warn(`visual pack: « ${effect} » stopped — too slow for this device`);
  for (const known of [...instances]) {
    if (baseOf(known.effect) === effect) {
      known.host.dataset.fxFailed = "true";
      instances.delete(known);
    }
  }
}

function still(): boolean {
  return reducedMotion() || motionBudget() === "still";
}

function loop(now: number) {
  frame = instances.size ? requestAnimationFrame(loop) : 0;
  if (!frame || document.hidden || now - last < frameInterval() - 2) return;
  last = now;
  const context = setup();
  if (!context) return;
  const frozen = still();
  // kept small (a ten-minute loop): even in medium precision the noise keeps moving
  const time = frozen ? 3.0 : ((now - started) / 1000) % 600;
  const visible = [...instances].filter((instance) => instance.visible);
  // issue 381: a look in a part of the page held still is drawn once, then holds
  const live = frozen
    ? new Set<Instance>()
    : moving(
        visible.filter((instance) => !stillFor(instance.host)),
        liveLooks(),
      );
  for (const instance of visible) {
    if (instance.drawn && !live.has(instance)) continue;
    const begun = performance.now();
    if (!draw(context, instance, time)) instance.host.dataset.fxFailed = "true";
    instance.drawn = true;
    if (externalFx(baseOf(instance.effect))) watch(instance, performance.now() - begun);
  }
}

export function attachFx(
  canvas: HTMLCanvasElement,
  host: HTMLElement,
  effect: string,
  options: FxOptions = {},
): (() => void) | null {
  if (!(FX_EFFECTS as readonly string[]).includes(baseOf(effect)) && !externalFx(baseOf(effect))) return null;
  if (GIVEN_UP.has(baseOf(effect))) return null;
  if (!setup()) return null;
  const context = canvas.getContext("2d");
  if (!context) return null;
  const instance: Instance = {
    canvas,
    host,
    effect,
    context,
    visible: true,
    drawn: false,
    seed: Math.random() * 10,
    born: performance.now() - (options.from ?? 0) * 1000,
    options,
    hovered: false,
  };
  instances.add(instance);
  // #29: pointed at or focused, it moves even when the budget holds it still
  const point = (hovered: boolean) => () => {
    instance.hovered = hovered;
  };
  const enter = point(true);
  const leave = point(false);
  host.addEventListener("pointerenter", enter);
  host.addEventListener("pointerleave", leave);
  host.addEventListener("focusin", enter);
  host.addEventListener("focusout", leave);
  if (typeof IntersectionObserver !== "undefined") {
    observer ??= new IntersectionObserver((entries) => {
      for (const entry of entries) {
        for (const known of instances) {
          if (known.canvas === entry.target) {
            known.visible = entry.isIntersecting;
            known.drawn = false;
            known.geometry = undefined;
          }
        }
      }
    });
    observer.observe(canvas);
  }
  if (!frame) frame = requestAnimationFrame(loop);
  return () => {
    instances.delete(instance);
    observer?.unobserve(canvas);
    host.removeEventListener("pointerenter", enter);
    host.removeEventListener("pointerleave", leave);
    host.removeEventListener("focusin", enter);
    host.removeEventListener("focusout", leave);
  };
}
