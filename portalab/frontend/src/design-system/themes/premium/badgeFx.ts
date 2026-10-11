/**
 * #73: level badges drawn by the GPU — living flames wrapped around the badge, electricity crackling over
 * it, water sloshing inside a glass badge, magma flowing under a cracked crust. One WebGL context for the
 * whole page (browsers allow few): each visible badge is drawn in turn into it and copied onto the badge's
 * own small 2D canvas. 30 frames a second at most, nothing while the tab is hidden or the badge off screen,
 * a still frame when motion is reduced. ``attachBadgeFx`` returns ``null`` when the device cannot draw it
 * (the badge then keeps its CSS look).
 */

export const FX_BADGES = ["blaze", "voltage", "aqua", "magma"] as const;
export type FxBadge = (typeof FX_BADGES)[number];

const HEAD = `
precision mediump float;
uniform vec2 u_res;
uniform float u_time;
uniform vec4 u_box; // the badge in the canvas: centre x, y and half width, height (pixels)
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
// the badge as a stadium: p in units of its half height; < 0 inside
float badge(vec2 p, float ax) {
  return length(max(abs(p) - vec2(ax - 1.0, 0.0), 0.0)) - 1.0;
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

const EFFECTS: Record<FxBadge, string> = {
  // living flames rising all around the badge, taller above it, over a body of glowing embers
  blaze: `
  vec2 q = vec2(p.x * 1.5, p.y * 1.1 - t * 2.4);
  float n = fbm(q + vec2(0.0, fbm(q * 1.7 + t * 0.6)) * 0.8);
  float reach = 0.25 + 1.1 * smoothstep(-1.0, 1.4, p.y);
  float f = 1.25 - max(d, 0.0) / (reach * (0.45 + 1.1 * n)) - 0.15 * noise(vec2(p.x * 4.0, t * 6.0));
  f *= smoothstep(-0.2, 0.05, d) * step(-1.6, p.y);
  vec3 fire = mix(vec3(0.75, 0.08, 0.02), vec3(1.0, 0.5, 0.05), smoothstep(0.25, 0.6, f));
  fire = mix(fire, vec3(1.0, 0.88, 0.45), smoothstep(0.65, 0.95, f));
  fire = mix(fire, vec3(1.0, 0.98, 0.9), smoothstep(0.95, 1.15, f));
  o = over(o, fire, smoothstep(0.18, 0.5, f));
  float ember = fbm(p * 3.0 + vec2(t * 0.3, -t * 0.5));
  vec3 body = mix(vec3(0.22, 0.03, 0.01), vec3(0.75, 0.16, 0.02), smoothstep(0.35, 0.75, ember));
  body = mix(body, vec3(1.0, 0.55, 0.1), smoothstep(0.7, 0.9, ember) * 0.8);
  body += vec3(1.0, 0.45, 0.08) * smoothstep(-0.25, 0.0, d) * 0.6;
  o = over(o, body, smoothstep(0.03, -0.03, d));
  for (int i = 0; i < 6; i++) {
    float fi = float(i);
    float life = fract(t * (0.5 + 0.3 * hash(vec2(fi, 1.0))) + hash(vec2(fi, 2.0)));
    vec2 s = vec2((hash(vec2(fi, 3.0)) - 0.5) * 2.0 * ax + sin(life * 6.0 + fi) * 0.2, 0.6 + life * 2.6);
    o = over(o, vec3(1.0, 0.7, 0.25), smoothstep(0.08, 0.0, length(p - s)) * (1.0 - life));
  }
`,
  // electricity: a charged badge, arcs crawling round its edge and leaping out, sparks inside
  voltage: `
  float flick = floor(t * 14.0);
  float pulse = 0.75 + 0.25 * noise(vec2(t * 9.0, 2.0));
  o = over(o, vec3(0.25, 0.45, 1.0), exp(-max(d, 0.0) * 3.2) * 0.45 * pulse * step(0.0, d));
  vec3 body = mix(vec3(0.03, 0.05, 0.16), vec3(0.08, 0.2, 0.5), fbm(p * 2.5 + t * 0.8));
  float inner = abs(fbm(p * 2.2 + vec2(flick * 0.37, flick * 0.21)) - 0.5);
  body += vec3(0.5, 0.85, 1.0) * smoothstep(0.03, 0.0, inner) * 0.9;
  body += vec3(0.4, 0.75, 1.0) * smoothstep(-0.3, 0.0, d) * 0.7;
  o = over(o, body, smoothstep(0.03, -0.03, d));
  float s = atan(p.y, p.x / ax);
  float glow = 0.0;
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float seg = step(0.45, noise(vec2(s * 1.6 + fi * 3.1, flick * 0.5 + fi * 7.0)));
    float off = 0.05 + 0.6 * noise(vec2(s * 7.0 + fi * 11.0, flick + fi * 5.0)) + 0.15 * noise(vec2(s * 23.0, flick * 1.3));
    float e = abs(d - off * (0.7 + 0.5 * fi));
    glow += seg * (0.02 / (e + 0.02)) * (0.85 - fi * 0.15);
  }
  o = over(o, vec3(0.35, 0.5, 1.0), smoothstep(0.15, 0.6, glow) * 0.35 * step(-0.05, d));
  o = over(o, mix(vec3(0.55, 0.75, 1.0), vec3(1.0), smoothstep(0.7, 1.4, glow)), smoothstep(0.45, 1.0, glow) * step(-0.05, d));
`,
  // a glass badge half full of water sloshing from side to side: waves, caustics, bubbles, a highlight
  aqua: `
  float tilt = 0.3 * sin(t * 0.9) + 0.1 * sin(t * 2.3);
  float surf = -0.05 + tilt * p.x / ax + 0.1 * sin(p.x * 3.0 + t * 3.0) + 0.05 * sin(p.x * 7.0 - t * 4.2);
  float inside = smoothstep(0.03, -0.03, d);
  vec3 glass = vec3(0.05, 0.1, 0.18) + vec3(0.2, 0.35, 0.5) * smoothstep(-0.35, 0.0, d);
  o = over(o, glass, inside * 0.9);
  float water = smoothstep(0.02, -0.02, p.y - surf) * inside;
  float depth = clamp((surf - p.y) / 2.0, 0.0, 1.0);
  vec3 w = mix(vec3(0.15, 0.75, 0.95), vec3(0.02, 0.22, 0.55), depth);
  float caustic = 1.0 - abs(2.0 * fbm(p * 2.6 + vec2(t * 0.6, t * 0.35)) - 1.0);
  w += vec3(0.6, 0.95, 1.0) * smoothstep(0.88, 0.98, caustic) * (1.0 - depth) * 0.7;
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    float life = fract(t * (0.35 + 0.25 * hash(vec2(fi, 4.0))) + hash(vec2(fi, 5.0)));
    vec2 b = vec2((hash(vec2(fi, 6.0)) - 0.5) * 1.6 * ax + sin(life * 9.0 + fi) * 0.08, -0.95 + life * 1.5);
    float r = 0.06 + 0.06 * hash(vec2(fi, 7.0));
    float ring = smoothstep(r, r * 0.6, length(p - b)) - smoothstep(r * 0.6, r * 0.2, length(p - b)) * 0.6;
    w = mix(w, vec3(0.85, 0.97, 1.0), ring * step(b.y, surf) * 0.8);
  }
  o = over(o, w, water * 0.95);
  o = over(o, vec3(0.85, 0.98, 1.0), smoothstep(0.05, 0.0, abs(p.y - surf)) * inside * 0.9);
  o = over(o, vec3(0.75, 0.9, 1.0), smoothstep(0.08, 0.0, abs(d + 0.03)) * 0.9);
  vec2 hl = (p - vec2(-ax * 0.45, 0.55)) / vec2(ax * 0.35, 0.12);
  o = over(o, vec3(1.0), smoothstep(1.0, 0.3, length(hl)) * inside * 0.55);
  o = over(o, vec3(0.3, 0.75, 1.0), exp(-max(d, 0.0) * 5.0) * 0.35 * step(0.0, d));
`,
  // magma: molten rock flowing under a dark cracked crust, its heat glowing around the badge
  magma: `
  vec2 flow = vec2(t * 0.25, -t * 0.12);
  float v = fbm(p * 1.8 + flow + fbm(p * 2.7 - flow * 1.3) * 0.9);
  float crack = 1.0 - abs(2.0 * fbm(p * 2.4 + flow * 0.6 + 4.0) - 1.0);
  vec3 crust = mix(vec3(0.08, 0.03, 0.02), vec3(0.22, 0.08, 0.04), v);
  vec3 lava = mix(vec3(0.85, 0.2, 0.02), vec3(1.0, 0.75, 0.2), smoothstep(0.6, 0.9, v));
  float molten = smoothstep(0.82, 0.96, crack) + smoothstep(0.62, 0.8, v) * 0.6;
  vec3 body = mix(crust, lava, clamp(molten, 0.0, 1.0));
  body += vec3(1.0, 0.4, 0.05) * smoothstep(-0.2, 0.0, d) * 0.5;
  float heat = exp(-max(d, 0.0) * 3.0) * (0.55 + 0.25 * noise(vec2(t * 3.0, 1.0)));
  o = over(o, vec3(1.0, 0.35, 0.05), heat * 0.55 * step(0.0, d));
  o = over(o, body, smoothstep(0.03, -0.03, d));
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float life = fract(t * (0.4 + 0.2 * hash(vec2(fi, 8.0))) + hash(vec2(fi, 9.0)));
    vec2 s = vec2((hash(vec2(fi, 10.0)) - 0.5) * 2.0 * ax, 0.9 + life * 1.8);
    o = over(o, vec3(1.0, 0.55, 0.15), smoothstep(0.07, 0.0, length(p - s)) * (1.0 - life));
  }
`,
};

// faded towards the canvas' edges: never a cut flame or a visible rectangle around the badge
const CLOSE = `
  float edge = min(min(gl_FragCoord.x, u_res.x - gl_FragCoord.x), min(gl_FragCoord.y, u_res.y - gl_FragCoord.y));
  gl_FragColor = o * smoothstep(0.0, u_box.w * 0.7, edge);
}`;

const VERTEX = `attribute vec2 a_pos;
void main() { gl_Position = vec4(a_pos, 0.0, 1.0); }`;

interface Program {
  program: WebGLProgram;
  res: WebGLUniformLocation | null;
  time: WebGLUniformLocation | null;
  box: WebGLUniformLocation | null;
}

interface Instance {
  canvas: HTMLCanvasElement;
  host: HTMLElement;
  effect: FxBadge;
  context: CanvasRenderingContext2D;
  visible: boolean;
  drawn: boolean;
  seed: number;
}

const FRAME_MS = 1000 / 30;
const MAX_SIDE = 512; // pixels of a badge's canvas, at most
let gl: WebGLRenderingContext | null = null;
let shared: HTMLCanvasElement | null = null;
let broken = false;
const programs = new Map<FxBadge, Program | null>();
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

function compile(context: WebGLRenderingContext, effect: FxBadge): Program | null {
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
  const fragment = make(context.FRAGMENT_SHADER, `${HEAD}${MAIN_OPEN}${EFFECTS[effect]}${CLOSE}`);
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

function draw(context: WebGLRenderingContext, instance: Instance, time: number): boolean {
  const program = compile(context, instance.effect);
  if (!program || !shared) return false;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const area = instance.canvas.getBoundingClientRect();
  const pill = instance.host.getBoundingClientRect();
  if (!area.width || !area.height) return true;
  const scale = Math.min(dpr, MAX_SIDE / Math.max(area.width, area.height));
  const w = Math.max(1, Math.round(area.width * scale));
  const h = Math.max(1, Math.round(area.height * scale));
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
  // the badge's rectangle in the canvas, y from the bottom (GL)
  const cx = (pill.left + pill.width / 2 - area.left) * scale;
  const cy = (area.bottom - (pill.top + pill.height / 2)) * scale;
  context.uniform4f(program.box, cx, cy, (pill.width / 2) * scale, (pill.height / 2) * scale);
  context.drawArrays(context.TRIANGLES, 0, 3);
  instance.context.clearRect(0, 0, w, h);
  instance.context.drawImage(shared, 0, shared.height - h, w, h, 0, 0, w, h);
  return true;
}

function loop(now: number) {
  frame = instances.size ? requestAnimationFrame(loop) : 0;
  if (!frame || document.hidden || now - last < FRAME_MS - 2) return;
  last = now;
  const context = setup();
  if (!context) return;
  const still = reducedMotion();
  const time = still ? 3.0 : (now - started) / 1000;
  for (const instance of instances) {
    if (!instance.visible || (still && instance.drawn)) continue;
    if (!draw(context, instance, time)) instance.host.dataset.fxFailed = "true";
    instance.drawn = true;
  }
}

export function attachBadgeFx(
  canvas: HTMLCanvasElement,
  host: HTMLElement,
  effect: FxBadge,
): (() => void) | null {
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
    seed: Math.random() * 100,
  };
  instances.add(instance);
  if (typeof IntersectionObserver !== "undefined") {
    observer ??= new IntersectionObserver((entries) => {
      for (const entry of entries) {
        for (const known of instances) {
          if (known.canvas === entry.target) {
            known.visible = entry.isIntersecting;
            known.drawn = false;
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
  };
}
