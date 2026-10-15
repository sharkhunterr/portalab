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

import { frameInterval, liveLooks, motionBudget } from "../../motion/budget";
import { externalFx } from "../external/external";
import { COSMOS_BADGE_EFFECTS, COSMOS_EFFECTS, COSMOS_STAGE_EFFECTS } from "./cosmosFx";

export const FX_EFFECTS = [
  "blaze",
  "voltage",
  "aqua",
  "magma",
  "glacier",
  "galaxy",
  "aurum",
  "toxic",
  "holo",
  "runes",
  "matrix",
  "sakura",
  "shadow",
  "candy",
  "aurora",
  "plasma",
  "chrono",
  // #81: the seasons' looks
  "spectre",
  "tinsel",
  "amour",
  "verdant",
  "sunburst",
  // full-stage level-up moments: drawn over the whole canvas, timed from when they start
  "supernova",
  "phoenix",
  "thunderstrike",
  "tidalwave",
  "arcanum",
  "sakurastorm",
  "goldrush",
  "aurorasky",
  "timeportal",
  // a stage's backdrop: drifting banks of fog under moving projectors (the booster opening)
  "mist",
  // a legendary card's moment on that stage
  "radiance",
  // issue 130: the cosmos
  ...COSMOS_BADGE_EFFECTS,
  ...COSMOS_STAGE_EFFECTS,
] as const;
export type FxBadge = (typeof FX_EFFECTS)[number];
const FULL_STAGE = new Set<string>([
  "supernova",
  "phoenix",
  "thunderstrike",
  "tidalwave",
  "arcanum",
  "sakurastorm",
  "goldrush",
  "aurorasky",
  "timeportal",
  "mist",
  "radiance",
  ...COSMOS_STAGE_EFFECTS,
]);

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

const EFFECTS: Record<FxBadge, string> = {
  ...COSMOS_EFFECTS, // issue 130
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
  // ice: a frozen body of facets, frost spikes growing from its edge, glints, a cold mist
  glacier: `
  vec2 cell = floor(p * 2.2 + 0.5 * vec2(noise(p * 1.3), noise(p * 1.3 + 4.0)));
  float facet = hash(cell);
  vec3 ice = mix(vec3(0.1, 0.32, 0.55), vec3(0.35, 0.65, 0.88), facet) * (0.8 + 0.25 * noise(p * 6.0));
  ice += vec3(0.85, 0.95, 1.0) * smoothstep(-0.14, 0.0, d) * 0.6;
  float ang = atan(p.y, p.x / ax);
  float spikes = pow(abs(sin(ang * 9.0 + noise(vec2(ang * 3.0, 1.0)) * 3.0)), 6.0);
  float grow = 0.12 + 0.38 * spikes * (0.6 + 0.4 * sin(t * 0.7 + ang * 2.0));
  float frost = smoothstep(grow, grow * 0.3, d) * step(0.0, d) * (0.6 + 0.4 * noise(p * 12.0));
  o = over(o, vec3(0.7, 0.9, 1.0), exp(-max(d, 0.0) * 3.5) * 0.25 * step(0.0, d));
  o = over(o, vec3(0.85, 0.95, 1.0), frost * 0.9);
  o = over(o, ice, smoothstep(0.03, -0.03, d));
  vec2 gp = fract(p * 8.0) - 0.5;
  float glint = step(0.97, hash(floor(p * 8.0) + floor(t * 2.0)));
  float star = glint * (smoothstep(0.07, 0.0, abs(gp.x)) + smoothstep(0.07, 0.0, abs(gp.y))) * smoothstep(0.5, 0.0, length(gp));
  o = over(o, vec3(1.0), star * step(d, 0.35));
`,
  // a spiral galaxy turning inside, stars glittering, a violet glow around
  galaxy: `
  vec2 g = vec2(p.x / max(ax, 1.0) * 1.2, p.y);
  float r = length(g);
  float a = atan(g.y, g.x);
  float arms = sin(a * 2.0 - log(r + 0.05) * 4.0 + t * 0.8);
  float neb = fbm(g * 2.5 + vec2(t * 0.1, -t * 0.07));
  vec3 col = mix(vec3(0.04, 0.02, 0.1), vec3(0.45, 0.12, 0.6), smoothstep(-0.2, 1.0, arms) * (1.0 - smoothstep(0.2, 1.4, r)));
  col += vec3(0.15, 0.3, 0.85) * neb * 0.5;
  col += vec3(1.0, 0.85, 0.95) * exp(-r * 6.0) * 0.9;
  vec2 sg = p * 9.0;
  float sh = hash(floor(sg));
  col += vec3(1.0) * step(0.92, sh) * smoothstep(0.35, 0.0, length(fract(sg) - 0.5)) * (0.5 + 0.5 * sin(t * 3.0 + sh * 40.0));
  col += vec3(0.6, 0.4, 1.0) * smoothstep(-0.25, 0.0, d) * 0.6;
  o = over(o, vec3(0.55, 0.3, 1.0), exp(-max(d, 0.0) * 4.0) * 0.4 * step(0.0, d));
  o = over(o, col, smoothstep(0.03, -0.03, d));
`,
  // liquid gold: a molten metal surface rippling, a shine sweeping across, a golden glow
  aurum: `
  vec2 w = p * 1.4 + vec2(fbm(p * 1.2 + t * 0.25), fbm(p * 1.2 - t * 0.2)) * 0.9;
  float h = fbm(w * 1.5 + t * 0.15);
  float hx = fbm((w + vec2(0.05, 0.0)) * 1.5 + t * 0.15) - h;
  float hy = fbm((w + vec2(0.0, 0.05)) * 1.5 + t * 0.15) - h;
  vec3 n = normalize(vec3(-hx * 14.0, -hy * 14.0, 1.0));
  vec3 l = normalize(vec3(-0.4, 0.6, 0.7));
  float diff = clamp(dot(n, l), 0.0, 1.0);
  float spec = pow(clamp(dot(reflect(-l, n), vec3(0.0, 0.0, 1.0)), 0.0, 1.0), 20.0);
  vec3 gold = mix(vec3(0.42, 0.25, 0.04), vec3(1.0, 0.78, 0.28), diff) + vec3(1.0, 0.95, 0.8) * spec * 0.8;
  float sweep = smoothstep(0.3, 0.0, abs(p.x + p.y * 0.5 - mod(t * 1.6, 2.0 * ax + 6.0) + ax + 3.0));
  gold += vec3(1.0, 0.95, 0.75) * sweep * 0.6;
  gold += vec3(1.0, 0.85, 0.4) * smoothstep(-0.2, 0.0, d) * 0.4;
  o = over(o, vec3(1.0, 0.75, 0.2), exp(-max(d, 0.0) * 4.5) * 0.35 * step(0.0, d));
  o = over(o, gold, smoothstep(0.03, -0.03, d));
`,
  // toxic: green acid bubbling inside, bubbles popping at its surface, drops dripping below, a sick glow
  toxic: `
  float surf = 0.55 + 0.06 * sin(p.x * 4.0 + t * 2.0) + 0.04 * sin(p.x * 9.0 - t * 3.0);
  float acid = fbm(p * 2.0 + vec2(0.0, -t * 0.6));
  vec3 body = mix(vec3(0.04, 0.22, 0.05), vec3(0.32, 0.85, 0.12), acid);
  body = mix(vec3(0.03, 0.08, 0.04), body, smoothstep(0.03, -0.03, p.y - surf));
  for (int i = 0; i < 6; i++) {
    float fi = float(i);
    float life = fract(t * (0.4 + 0.3 * hash(vec2(fi, 11.0))) + hash(vec2(fi, 12.0)));
    vec2 b = vec2((hash(vec2(fi, 13.0)) - 0.5) * 1.7 * ax, -0.9 + life * (surf + 0.9));
    float r = 0.07 + 0.07 * hash(vec2(fi, 14.0));
    float ring = smoothstep(r, r * 0.7, length(p - b)) - smoothstep(r * 0.7, r * 0.3, length(p - b)) * 0.7;
    body = mix(body, vec3(0.7, 1.0, 0.45), ring * 0.8);
  }
  body += vec3(0.6, 1.0, 0.3) * smoothstep(-0.2, 0.0, d) * 0.5;
  o = over(o, vec3(0.4, 1.0, 0.2), exp(-max(d, 0.0) * 3.5) * 0.4 * step(0.0, d));
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float x = (hash(vec2(fi, 15.0)) - 0.5) * 1.6 * ax;
    float life = fract(t * 0.35 + hash(vec2(fi, 16.0)));
    float y = -1.0 - life * life * 2.2;
    float drop = smoothstep(0.1, 0.0, length((p - vec2(x, y)) * vec2(1.0, 0.75))) * (1.0 - life);
    float thread = smoothstep(0.03, 0.0, abs(p.x - x)) * step(y, p.y) * step(p.y, -0.95) * step(life, 0.25);
    o = over(o, vec3(0.45, 1.0, 0.2), clamp(drop + thread, 0.0, 1.0));
  }
  o = over(o, body, smoothstep(0.03, -0.03, d));
`,
  // holographic foil: rainbow sheen sliding with the light, a shine band, fine scanlines, a neon edge
  holo: `
  float sweep = p.x * 0.35 + p.y * 0.6 + t * 0.5;
  vec3 irid = 0.5 + 0.5 * cos(6.2831 * (sweep + fbm(p * 2.0) * 0.6 + vec3(0.0, 0.33, 0.67)));
  irid = mix(vec3(0.08, 0.06, 0.15), irid, 0.6);
  float lines = 0.85 + 0.15 * sin(gl_FragCoord.y * 1.3 + t * 6.0);
  float band = smoothstep(0.35, 0.0, abs(p.x - p.y * 0.4 - mod(t * 2.0, 2.0 * ax + 4.0) + ax + 2.0));
  vec3 body = irid * lines + vec3(1.0) * band * 0.45;
  body += vec3(0.9, 0.5, 1.0) * smoothstep(-0.15, 0.0, d) * 0.6;
  vec3 neon = mix(vec3(0.0, 1.0, 1.0), vec3(1.0, 0.2, 0.9), 0.5 + 0.5 * sin(t * 2.0 + p.x));
  o = over(o, neon, exp(-max(d, 0.0) * 5.0) * 0.45 * step(0.0, d));
  o = over(o, body, smoothstep(0.03, -0.03, d));
`,
  // arcane runes: a ring of glyphs orbiting the edge, a deep swirling mist inside, motes rising
  runes: `
  float ang = atan(p.y, p.x / ax) + t * 0.4;
  float id = floor(ang / 6.2831 * 12.0);
  float u = fract(ang / 6.2831 * 12.0);
  float band = (d - 0.1) / 0.28;
  vec2 lc = vec2(u, band) * 3.0;
  vec2 gc = floor(lc);
  vec2 gf = fract(lc);
  float stroke = step(0.45, hash(gc + id * 7.0)) * smoothstep(0.22, 0.0, abs(gf.x - 0.5))
               + step(0.6, hash(gc + id * 3.0)) * smoothstep(0.22, 0.0, abs(gf.y - 0.5));
  float rune = clamp(stroke, 0.0, 1.0) * step(0.0, band) * step(band, 1.0) * step(0.15, u) * step(u, 0.85);
  float pulse = 0.6 + 0.4 * sin(t * 2.0 + id);
  o = over(o, vec3(0.35, 0.75, 1.0), exp(-abs(d - 0.24) * 8.0) * 0.25 * step(0.0, d));
  o = over(o, vec3(0.65, 0.9, 1.0), rune * pulse);
  vec2 sw = p + vec2(fbm(p * 1.5 + t * 0.2), fbm(p * 1.5 - t * 0.15)) * 0.8;
  vec3 body = mix(vec3(0.05, 0.03, 0.18), vec3(0.28, 0.15, 0.62), fbm(sw * 2.0));
  body += vec3(1.0, 0.8, 0.35) * smoothstep(-0.12, 0.0, d) * 0.55;
  for (int i = 0; i < 6; i++) {
    float fi = float(i);
    float life = fract(t * (0.3 + 0.2 * hash(vec2(fi, 21.0))) + hash(vec2(fi, 22.0)));
    vec2 m = vec2((hash(vec2(fi, 23.0)) - 0.5) * 1.6 * ax, -0.9 + life * 1.8);
    body += vec3(0.7, 0.9, 1.0) * smoothstep(0.08, 0.0, length(p - m)) * (1.0 - life);
  }
  o = over(o, body, smoothstep(0.03, -0.03, d));
`,
  // digital rain: glyphs falling in columns inside, bright heads, a green glow
  matrix: `
  vec2 g = p * 4.0;
  float col = floor(g.x);
  float sp = 1.5 + 2.0 * hash(vec2(col, 1.0));
  vec2 cell = vec2(col, floor(g.y + t * sp));
  float stream = pow(fract(g.y * 0.17 + t * sp * 0.25 + hash(vec2(col, 3.0))), 3.0);
  vec2 f = fract(vec2(g.x, g.y + t * sp));
  vec2 sub = floor(f * 3.0);
  float bit = step(0.4, hash(cell * 1.3 + sub + floor(t * 5.0 + hash(cell) * 3.0)));
  float glyph = bit * step(0.12, f.x) * step(f.x, 0.88) * step(0.12, f.y) * step(f.y, 0.88);
  vec3 body = vec3(0.0, 0.05, 0.02) + vec3(0.15, 0.95, 0.35) * glyph * stream;
  body += vec3(0.8, 1.0, 0.85) * glyph * step(0.94, stream);
  body += vec3(0.2, 1.0, 0.4) * smoothstep(-0.12, 0.0, d) * 0.5;
  o = over(o, vec3(0.1, 1.0, 0.35), exp(-max(d, 0.0) * 5.0) * 0.35 * step(0.0, d));
  o = over(o, body, smoothstep(0.03, -0.03, d));
`,
  // sakura: petals drifting round in the breeze, a soft pink glow inside
  sakura: `
  vec3 body = mix(vec3(0.3, 0.06, 0.17), vec3(0.75, 0.32, 0.5), 0.5 + 0.5 * sin(p.x * 1.5 + t * 0.5) * fbm(p * 2.0));
  body += vec3(1.0, 0.8, 0.9) * smoothstep(-0.2, 0.0, d) * 0.5;
  o = over(o, vec3(1.0, 0.6, 0.8), exp(-max(d, 0.0) * 4.0) * 0.3 * step(0.0, d));
  o = over(o, body, smoothstep(0.03, -0.03, d));
  for (int i = 0; i < 10; i++) {
    float fi = float(i);
    float life = fract(t * 0.12 * (1.0 + hash(vec2(fi, 31.0))) + hash(vec2(fi, 32.0)));
    vec2 pos = vec2(-ax - 1.0 + life * (2.0 * ax + 2.0), 1.4 - life * 2.8 + 0.3 * sin(life * 6.0 + fi));
    float rot = t * 2.0 + fi;
    vec2 q = mat2(cos(rot), -sin(rot), sin(rot), cos(rot)) * (p - pos) / 0.14;
    float petal = smoothstep(1.0, 0.75, length(q * vec2(1.0, 1.8))) * smoothstep(-0.1, 0.25, q.x + abs(q.y) * 1.2);
    o = over(o, mix(vec3(1.0, 0.72, 0.85), vec3(0.95, 0.45, 0.65), smoothstep(-0.8, 0.8, q.x)), petal * 0.95);
  }
`,
  // shadow: black smoke reaching out from it, faint red veins, eyes opening in the dark
  shadow: `
  float smoke = fbm(p * 1.8 + vec2(t * 0.3, t * 0.5) + fbm(p * 2.5 - t * 0.2));
  float reach = 0.15 + 0.7 * smoke;
  o = over(o, vec3(0.5, 0.0, 0.05), exp(-abs(d - reach * 0.6) * 10.0) * 0.18 * step(0.0, d));
  o = over(o, vec3(0.02, 0.0, 0.02), smoothstep(reach, 0.0, d) * step(0.0, d) * 0.85);
  vec3 body = vec3(0.03, 0.01, 0.03);
  body += vec3(0.5, 0.02, 0.05) * smoothstep(0.93, 0.99, 1.0 - abs(2.0 * fbm(p * 3.0 + t * 0.1) - 1.0));
  float blink = step(0.08, abs(fract(t * 0.23) - 0.5));
  float open = smoothstep(0.0, 0.4, fract(t * 0.11)) * blink;
  for (int j = 0; j < 2; j++) {
    vec2 e = p - vec2((j == 0 ? -0.35 : 0.35) * min(ax, 1.5), 0.15);
    float eye = smoothstep(0.0, 0.2, 1.0 - length(vec2(e.x / 0.16, e.y / (0.07 * max(open, 0.05)) + abs(e.x) * 4.0)));
    body = mix(body, vec3(1.0, 0.15, 0.05), eye);
  }
  body += vec3(0.4, 0.0, 0.05) * smoothstep(-0.15, 0.0, d) * 0.6;
  o = over(o, body, smoothstep(0.03, -0.03, d));
`,
  // candy: pastel stripes swirling, sprinkles, a glossy shine and twinkling stars around
  candy: `
  float a = atan(p.y, p.x / max(ax, 1.0));
  float r = length(vec2(p.x / max(ax, 1.0), p.y));
  float k = fract((a * 3.0 + r * 5.0 - t * 1.6) / 6.2831);
  vec3 c1 = vec3(1.0, 0.45, 0.7);
  vec3 c2 = vec3(0.5, 0.82, 1.0);
  vec3 c3 = vec3(1.0, 0.88, 0.45);
  vec3 body = k < 0.33 ? mix(c1, c2, smoothstep(0.28, 0.33, k)) : k < 0.66 ? mix(c2, c3, smoothstep(0.61, 0.66, k)) : mix(c3, c1, smoothstep(0.95, 1.0, k));
  vec2 sg = p * 5.0;
  vec2 sid = floor(sg);
  float sa = hash(sid) * 3.1416;
  vec2 sq = mat2(cos(sa), -sin(sa), sin(sa), cos(sa)) * (fract(sg) - 0.5);
  float sprinkle = step(0.55, hash(sid + 3.0)) * smoothstep(0.05, 0.0, abs(sq.y)) * step(abs(sq.x), 0.2);
  body = mix(body, 0.5 + 0.5 * cos(6.2831 * (hash(sid + 5.0) + vec3(0.0, 0.33, 0.67))), sprinkle);
  body = mix(body, vec3(0.25, 0.1, 0.3), 0.25);
  body += vec3(1.0) * smoothstep(0.15, 0.0, abs(p.y - 0.6)) * smoothstep(-0.05, -0.3, d) * 0.35;
  body += vec3(1.0, 0.9, 1.0) * smoothstep(-0.15, 0.0, d) * 0.5;
  o = over(o, body, smoothstep(0.03, -0.03, d));
  vec2 tg = p * 3.0;
  vec2 tc = fract(tg) - 0.5;
  float tw = step(0.8, hash(floor(tg) + 9.0)) * (0.5 + 0.5 * sin(t * 4.0 + hash(floor(tg)) * 30.0));
  float twinkle = (smoothstep(0.05, 0.0, abs(tc.x)) + smoothstep(0.05, 0.0, abs(tc.y))) * smoothstep(0.35, 0.0, length(tc));
  o = over(o, vec3(1.0, 0.85, 0.95), twinkle * tw * step(0.05, d) * smoothstep(0.9, 0.2, d));
`,
  // aurora: green and violet curtains waving in a night sky, stars, a cold glow
  aurora: `
  vec3 body = mix(vec3(0.01, 0.03, 0.09), vec3(0.03, 0.09, 0.2), p.y * 0.5 + 0.5);
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float x = p.x * 0.8 + fbm(vec2(p.x * 0.7 + fi * 3.0, t * 0.15)) * 1.5;
    float centre = 0.1 + 0.25 * sin(x * 2.0 + t * 0.5 + fi * 2.0);
    float curtain = exp(-pow((p.y - centre) * 2.6, 2.0)) * smoothstep(-1.0, centre, p.y);
    float rays = 0.55 + 0.45 * sin(p.x * 22.0 + fbm(vec2(p.x * 3.0, t * 0.3 + fi)) * 10.0);
    vec3 c = fi < 0.5 ? vec3(0.2, 1.0, 0.55) : fi < 1.5 ? vec3(0.2, 0.85, 0.9) : vec3(0.65, 0.35, 1.0);
    body += c * curtain * rays * 0.55;
  }
  vec2 sg = p * 8.0;
  body += vec3(1.0) * step(0.95, hash(floor(sg))) * smoothstep(0.3, 0.0, length(fract(sg) - 0.5)) * 0.8;
  body += vec3(0.5, 1.0, 0.8) * smoothstep(-0.15, 0.0, d) * 0.45;
  o = over(o, vec3(0.3, 1.0, 0.6), exp(-max(d, 0.0) * 4.5) * 0.3 * step(0.0, d));
  o = over(o, body, smoothstep(0.03, -0.03, d));
`,
  // plasma ball: filaments of light reaching from a bright core to the glass, flickering
  plasma: `
  vec2 c = vec2(p.x / max(ax, 1.0), p.y);
  float r = length(c);
  float a = atan(c.y, c.x);
  float fil = 0.0;
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    float phi = fi * 1.2566 + t * 0.4 + (noise(vec2(r * 4.0, t * 1.5 + fi * 3.0)) - 0.5) * 1.6;
    float da = abs(mod(a - phi + 3.1416, 6.2831) - 3.1416);
    fil += 0.03 / (da * r * 3.0 + 0.03) * smoothstep(1.05, 0.15, r);
  }
  vec3 body = vec3(0.06, 0.01, 0.12) + vec3(1.0, 0.3, 0.9) * fil * 0.35 + vec3(1.0, 0.85, 1.0) * exp(-r * 5.0);
  body += vec3(0.8, 0.6, 1.0) * smoothstep(-0.12, 0.0, d) * 0.55;
  o = over(o, vec3(0.9, 0.3, 1.0), exp(-max(d, 0.0) * 4.5) * 0.4 * step(0.0, d));
  o = over(o, body, smoothstep(0.03, -0.03, d));
`,
  // —— full-stage level-up moments: c in units of the stage height, centred; tl the moment's own time ——
  // #81 spectre (Halloween): ghostly wisps rising from it, a smoky body, faint eyes drifting in the smoke
  spectre: `
  vec2 q = vec2(p.x * 1.2, p.y * 0.9 - t * 0.7);
  float wisp = fbm(q * 1.6 + vec2(fbm(q * 2.2 + t * 0.3) * 1.2, 0.0));
  float reach = 0.2 + 1.0 * smoothstep(-1.0, 1.5, p.y);
  float f = (1.2 - max(d, 0.0) / (reach * (0.4 + wisp))) * smoothstep(-0.2, 0.05, d);
  vec3 ghost = mix(vec3(0.15, 0.55, 0.5), vec3(0.78, 1.0, 0.93), smoothstep(0.4, 1.0, f));
  o = over(o, ghost, smoothstep(0.25, 0.7, f) * 0.85);
  vec3 body = mix(vec3(0.06, 0.03, 0.12), vec3(0.18, 0.36, 0.34), fbm(p * 2.0 + vec2(0.0, -t * 0.4)));
  body += vec3(0.5, 1.0, 0.85) * smoothstep(-0.2, 0.0, d) * 0.5;
  o = over(o, body, smoothstep(0.03, -0.03, d));
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float life = fract(t * 0.18 + hash(vec2(fi, 7.0)));
    vec2 pos = vec2((hash(vec2(fi, 8.0)) - 0.5) * 2.0 * ax, -0.6 + life * 2.4);
    float eyes = smoothstep(0.07, 0.0, length(p - pos - vec2(0.09, 0.0)))
      + smoothstep(0.07, 0.0, length(p - pos + vec2(0.09, 0.0)));
    o = over(o, vec3(0.8, 1.0, 0.9), eyes * sin(life * 3.14159) * 0.9);
  }
`,
  // #81 tinsel (Christmas): gold and green tinsel twisting around it, glitter, a warm red body
  tinsel: `
  float s = atan(p.y, p.x / max(ax, 0.001));
  float band = exp(-pow(max(d, 0.0) * 6.0 - 0.35, 2.0) * 6.0) * step(0.0, d);
  float twist = 0.5 + 0.5 * sin(s * 18.0 + d * 40.0 - t * 2.5);
  vec3 col = mix(vec3(0.95, 0.75, 0.2), vec3(0.15, 0.75, 0.35), step(0.5, fract(s * 1.4 + t * 0.05)));
  o = over(o, col, band * (0.45 + 0.55 * twist));
  vec2 g = p * 14.0;
  float glint = step(0.9, hash(floor(g) + floor(t * 6.0))) * smoothstep(0.35, 0.0, length(fract(g) - 0.5));
  o = over(o, vec3(1.0, 0.97, 0.8), glint * band * 1.5);
  o = over(o, vec3(1.0, 0.85, 0.35), exp(-max(d, 0.0) * 5.0) * 0.25 * step(0.0, d));
  vec3 body = mix(vec3(0.35, 0.03, 0.06), vec3(0.6, 0.12, 0.1), fbm(p * 2.5 + t * 0.2));
  body += vec3(1.0, 0.8, 0.3) * smoothstep(-0.18, 0.0, d) * 0.6;
  o = over(o, body, smoothstep(0.03, -0.03, d));
`,
  // #81 amour (Valentine's Day): pink and red light swirling round it, little hearts rising
  amour: `
  float sw = fbm(vec2(atan(p.y, p.x) * 2.0 + t * 0.6, length(p) * 2.0 - t * 0.8));
  vec3 glow = mix(vec3(0.9, 0.15, 0.35), vec3(1.0, 0.6, 0.75), sw);
  o = over(o, glow, exp(-max(d, 0.0) * 3.5) * (0.35 + 0.4 * sw) * step(0.0, d));
  vec3 body = mix(vec3(0.3, 0.02, 0.1), vec3(0.85, 0.2, 0.4), fbm(p * 2.0 + vec2(t * 0.3, 0.0)));
  body += vec3(1.0, 0.7, 0.8) * smoothstep(-0.18, 0.0, d) * 0.5;
  o = over(o, body, smoothstep(0.03, -0.03, d));
  for (int i = 0; i < 8; i++) {
    float fi = float(i);
    float life = fract(t * 0.2 * (1.0 + hash(vec2(fi, 41.0))) + hash(vec2(fi, 42.0)));
    vec2 pos = vec2((hash(vec2(fi, 43.0)) - 0.5) * 2.2 * ax + 0.15 * sin(life * 8.0 + fi), -1.1 + life * 2.8);
    vec2 h = (p - pos) / 0.12;
    h.x = abs(h.x);
    float hd = length(vec2(h.x, h.y - sqrt(h.x) * 0.55)) - 1.0;
    o = over(o, vec3(1.0, 0.35, 0.55), smoothstep(0.12, -0.12, hd) * sin(life * 3.14159) * 0.95);
  }
`,
  // #81 verdant (spring): leaves of light growing all around it, swaying, pollen rising
  verdant: `
  float s = atan(p.y, p.x / max(ax, 0.001));
  float n = 9.0;
  float cell = floor((s + 3.14159) / 6.28318 * n);
  float local = fract((s + 3.14159) / 6.28318 * n) - 0.5 + 0.08 * sin(t * 1.3 + cell);
  float grow = 0.5 + 0.5 * sin(t * 0.8 + cell * 1.7);
  float len = 0.25 + 0.35 * grow;
  float r = max(d, 0.0);
  float k = clamp(r / len, 0.0, 1.0);
  float leaf = smoothstep(0.03, 0.0, abs(local) * 2.2 - sin(k * 3.14159) * 0.9) * step(r, len) * step(0.0, d);
  o = over(o, mix(vec3(0.2, 0.7, 0.3), vec3(0.78, 1.0, 0.45), k), leaf * 0.9);
  o = over(o, vec3(0.6, 1.0, 0.5), exp(-r * 4.0) * 0.3 * step(0.0, d));
  vec3 body = mix(vec3(0.03, 0.15, 0.06), vec3(0.2, 0.45, 0.2), fbm(p * 2.2 + t * 0.15));
  body += vec3(0.8, 1.0, 0.6) * smoothstep(-0.18, 0.0, d) * 0.5;
  o = over(o, body, smoothstep(0.03, -0.03, d));
  for (int i = 0; i < 8; i++) {
    float fi = float(i);
    float life = fract(t * 0.25 + hash(vec2(fi, 51.0)));
    vec2 pos = vec2((hash(vec2(fi, 52.0)) - 0.5) * 2.4 * ax + 0.1 * sin(life * 9.0), -1.0 + life * 2.6);
    o = over(o, vec3(1.0, 0.95, 0.5), smoothstep(0.05, 0.0, length(p - pos)) * sin(life * 3.14159));
  }
`,
  // #81 sunburst (summer): a blazing sun — rays flaring out and turning slowly, a molten bright body
  sunburst: `
  float s = atan(p.y, p.x / max(ax, 0.001));
  float r = max(d, 0.0);
  float rays = pow(0.5 + 0.5 * sin(s * 16.0 + t * 0.6), 6.0) + 0.6 * pow(0.5 + 0.5 * sin(s * 7.0 - t * 0.4 + 1.3), 4.0);
  float flare = exp(-r * (2.2 + 3.0 * (1.0 - min(rays, 1.0)))) * step(0.0, d);
  vec3 sun = mix(vec3(1.0, 0.45, 0.1), vec3(1.0, 0.92, 0.55), exp(-r * 3.0));
  o = over(o, sun, flare * (0.5 + 0.4 * noise(vec2(s * 6.0, t * 2.0))));
  vec3 body = mix(vec3(1.0, 0.55, 0.12), vec3(1.0, 0.93, 0.6), fbm(p * 2.5 + vec2(t * 0.3, -t * 0.2)));
  body += vec3(1.0, 1.0, 0.85) * smoothstep(-0.2, 0.0, d) * 0.4;
  o = over(o, body, smoothstep(0.03, -0.03, d));
`,
  // supernova: a star gathers, bursts in a flash, a shock wave rings out, debris and a nebula afterglow
  supernova: `
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float r = length(c);
  float tl = mod(u_age, 7.0);
  float burst = 0.7;
  float after = max(tl - burst, 0.0);
  float gather = smoothstep(0.0, burst, tl) * step(tl, burst);
  o = over(o, vec3(1.0, 0.95, 0.85), exp(-r * (40.0 - 30.0 * gather)) * (0.4 + 0.6 * gather));
  float flash = exp(-after * 5.0) * step(burst, tl);
  o = over(o, vec3(1.0, 0.97, 0.9), flash * exp(-r * 1.5) * 0.9);
  float wave = after * 0.7;
  o = over(o, vec3(0.6, 0.8, 1.0), exp(-abs(r - wave) * 30.0) * step(burst, tl) * exp(-after * 0.5));
  float neb = fbm(c * 3.0 + vec2(after * 0.05, 0.0)) * smoothstep(wave, wave * 0.4, r) * step(burst, tl);
  vec3 nc = mix(vec3(0.5, 0.15, 0.8), vec3(1.0, 0.45, 0.25), fbm(c * 5.0 + 3.0));
  o = over(o, nc, neb * 0.75 * exp(-max(after - 2.5, 0.0) * 0.6));
  float rays = pow(noise(vec2(atan(c.y, c.x) * 18.0, 1.0)), 6.0) * smoothstep(wave, wave * 0.5, r) * step(burst, tl);
  o = over(o, vec3(1.0, 0.9, 0.7), rays * exp(-after * 0.8));
  vec2 sg = c * 30.0;
  o = over(o, vec3(1.0), step(0.985, hash(floor(sg))) * smoothstep(0.4, 0.0, length(fract(sg) - 0.5)) * 0.6);
  o *= smoothstep(7.0, 6.0, tl);
`,
  // phoenix: fire rises from below, a bird of flame spreads its wings, embers fly up
  phoenix: `
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float tt = u_age;
  float height = smoothstep(0.0, 1.2, tl) * 0.45;
  float n = fbm(vec2(c.x * 4.0, c.y * 3.0 - tt * 2.2));
  float floorFire = clamp((height - uv.y) / max(height, 0.01) + (n - 0.5) * 0.9, 0.0, 1.0);
  vec3 fire = mix(vec3(0.7, 0.08, 0.02), vec3(1.0, 0.55, 0.08), floorFire);
  fire = mix(fire, vec3(1.0, 0.92, 0.6), smoothstep(0.75, 1.0, floorFire));
  o = over(o, fire, smoothstep(0.15, 0.5, floorFire) * 0.9);
  float open = smoothstep(1.0, 2.4, tl);
  float beat = sin(tt * 2.2) * 0.06 * open;
  vec2 q = vec2(abs(c.x), c.y - 0.08);
  float span = 0.8 * open + 0.001;
  float x = clamp(q.x / span, 0.0, 1.0);
  // the wing: a raised leading edge, long feathers hanging from it, ragged with flame
  float top = (0.26 * sin(x * 2.6) - 0.1 * x * x) * open + beat * x;
  float feathers = 0.07 + 0.16 * x + 0.16 * pow(abs(sin(x * 11.0 + 0.4)), 3.0) * x;
  float flick = (fbm(vec2(q.x * 7.0, q.y * 5.0 - tt * 2.5)) - 0.5) * 0.08;
  float wing = smoothstep(0.015, -0.015, q.y - top - flick) * smoothstep(-0.015, 0.015, q.y - (top - feathers) - flick);
  wing *= smoothstep(span, span * 0.82, q.x);
  float shade = clamp((q.y - (top - feathers)) / max(feathers, 0.01), 0.0, 1.0);
  float body = smoothstep(0.075, 0.0, length((c - vec2(0.0, 0.07)) * vec2(1.5, 1.1))) * open;
  float head = smoothstep(0.04, 0.0, length(c - vec2(0.0, 0.17 + beat * 0.3))) * open;
  vec2 tq = c - vec2(0.0, 0.0);
  float sway = sin(tq.y * 9.0 + tt * 4.0) * 0.025;
  float tongue = (0.07 * (1.0 + tq.y * 2.4) - abs(tq.x + sway)) * 14.0 + (fbm(vec2(tq.x * 9.0, tq.y * 5.0 + tt * 3.5)) - 0.5) * 2.2;
  float tail = smoothstep(0.1, 0.6, tongue) * step(tq.y, 0.02) * step(-0.42, tq.y) * open;
  float bird = clamp(wing + body + head + tail, 0.0, 1.0);
  vec3 bc = mix(vec3(0.95, 0.25, 0.04), vec3(1.0, 0.75, 0.25), shade);
  bc = mix(bc, vec3(1.0, 0.95, 0.75), clamp(body + head, 0.0, 1.0) * 0.8);
  o = over(o, vec3(1.0, 0.45, 0.1), exp(-length(c - vec2(0.0, 0.1)) * 3.0) * 0.35 * open);
  o = over(o, bc, bird * 0.95);
  for (int i = 0; i < 24; i++) {
    float fi = float(i);
    float life = fract(tt * (0.25 + 0.2 * hash(vec2(fi, 41.0))) + hash(vec2(fi, 42.0)));
    vec2 e = vec2((hash(vec2(fi, 43.0)) - 0.5) * 1.8 + sin(life * 6.0 + fi) * 0.05, -0.55 + life * 1.2);
    o = over(o, vec3(1.0, 0.65, 0.2), smoothstep(0.012, 0.0, length(c - e)) * (1.0 - life));
  }
  o *= smoothstep(7.0, 6.0, tl);
`,
  // thunderstrike: storm clouds roll in, bolts strike one after another, the sky flashes, rain falls
  thunderstrike: `
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float tt = u_age;
  float cloud = fbm(vec2(c.x * 2.0 + tt * 0.1, c.y * 3.0)) * smoothstep(0.2, 0.9, uv.y);
  float flash = 0.0;
  float bolts = 0.0;
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    float at = 0.3 + fk * 0.95;
    float age = tl - at;
    float on = step(0.0, age) * step(age, 0.5) * step(0.25, noise(vec2(age * 30.0, fk)));
    flash += exp(-max(age, 0.0) * 6.0) * step(0.0, age);
    float x0 = (hash(vec2(fk, floor(u_age / 7.0))) - 0.5) * 1.2;
    float y = c.y;
    float path = x0 + (fbm(vec2(y * 6.0, fk * 9.0 + floor(u_age / 7.0))) - 0.5) * 0.35 * (0.5 - y);
    float branch = x0 + (fbm(vec2(y * 7.0, fk * 4.0)) - 0.5) * 0.5 * (0.5 - y) + (0.3 - y) * 0.4 * (hash(vec2(fk, 2.0)) - 0.5);
    float bolt = 0.004 / (abs(c.x - path) + 0.004) + 0.4 * step(y, 0.3) * 0.003 / (abs(c.x - branch) + 0.003) * step(-0.1, y);
    bolts += bolt * on * step(-0.5, y);
  }
  vec3 sky = mix(vec3(0.05, 0.06, 0.1), vec3(0.25, 0.27, 0.35), cloud);
  o = over(o, sky, smoothstep(0.35, 0.8, uv.y) * 0.85);
  o = over(o, vec3(0.75, 0.8, 1.0), clamp(flash, 0.0, 1.0) * 0.35);
  o = over(o, mix(vec3(0.6, 0.7, 1.0), vec3(1.0), smoothstep(1.0, 3.0, bolts)), smoothstep(0.4, 1.5, bolts));
  float rx = floor(gl_FragCoord.x / 5.0);
  float ry = gl_FragCoord.y / 26.0 + tt * 26.0 + hash(vec2(rx, 1.0)) * 20.0;
  float rain = step(0.985, hash(vec2(rx, floor(ry)))) * smoothstep(1.2, 0.0, abs(mod(gl_FragCoord.x, 5.0) - 2.5)) * smoothstep(0.0, 0.6, fract(ry));
  o = over(o, vec3(0.65, 0.75, 0.95), rain * 0.25);
  o *= smoothstep(7.0, 6.0, tl);
`,
  // tidal wave: water rises, a great wave rolls across with its foam and spray, then draws back
  tidalwave: `
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float tt = u_age;
  float aspect = u_res.x / u_res.y;
  float level = smoothstep(0.0, 1.4, tl) * 0.38 * smoothstep(6.5, 5.0, tl);
  float crestX = -aspect * 0.6 + (tl - 0.6) * aspect * 0.45;
  float bump = 0.32 * exp(-pow((c.x - crestX) * 2.4, 2.0)) * smoothstep(0.4, 1.2, tl) * smoothstep(6.0, 4.0, tl);
  float surf = level + bump + 0.025 * sin(c.x * 10.0 - tt * 3.0) + 0.015 * sin(c.x * 23.0 + tt * 4.0);
  float depth = clamp((surf - uv.y) * 3.0, 0.0, 1.0);
  vec3 water = mix(vec3(0.25, 0.75, 0.9), vec3(0.02, 0.15, 0.35), depth);
  float caustic = 1.0 - abs(2.0 * fbm(c * 6.0 + vec2(tt * 0.5, tt * 0.3)) - 1.0);
  water += vec3(0.6, 0.95, 1.0) * smoothstep(0.9, 0.99, caustic) * (1.0 - depth) * 0.6;
  o = over(o, water, step(uv.y, surf) * 0.88);
  float foam = smoothstep(0.03, 0.0, abs(uv.y - surf)) * (0.6 + 0.4 * noise(vec2(c.x * 30.0, tt * 3.0)));
  foam += smoothstep(0.08, 0.0, abs(uv.y - surf)) * exp(-pow((c.x - crestX) * 4.0, 2.0)) * fbm(c * 20.0 + tt);
  o = over(o, vec3(0.95, 1.0, 1.0), clamp(foam, 0.0, 1.0) * 0.9);
  for (int i = 0; i < 24; i++) {
    float fi = float(i);
    float life = fract(tt * (0.6 + 0.4 * hash(vec2(fi, 51.0))) + hash(vec2(fi, 52.0)));
    vec2 sp = vec2(crestX + (hash(vec2(fi, 53.0)) - 0.3) * 0.3 + life * 0.25, level + bump - 0.5 + life * 0.25 - life * life * 0.3);
    o = over(o, vec3(0.9, 0.97, 1.0), smoothstep(0.01, 0.0, length(c - sp)) * (1.0 - life) * smoothstep(0.4, 1.2, tl));
  }
`,
  // arcanum: a magic circle draws itself — rings, a hexagram, runes turning — then flares; motes rise
  arcanum: `
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float r = length(c);
  float a = atan(c.y, c.x);
  float tl = mod(u_age, 7.0);
  float drawn = smoothstep(0.0, 1.6, tl);
  float reveal = step(mod(a + 3.1416, 6.2832), drawn * 6.2832);
  float rings = (exp(-abs(r - 0.42) * 120.0) + exp(-abs(r - 0.36) * 140.0) + exp(-abs(r - 0.2) * 140.0)) * reveal;
  vec2 hx = c / 0.36;
  float tri = 0.0;
  for (int i = 0; i < 2; i++) {
    float rot = float(i) * 3.1416 + u_age * 0.2;
    vec2 q = mat2(cos(rot), -sin(rot), sin(rot), cos(rot)) * hx;
    float e = max(abs(q.x) * 0.866 + q.y * 0.5, -q.y) - 0.5;
    tri += exp(-abs(e) * 40.0);
  }
  tri *= smoothstep(0.8, 2.0, tl);
  float ra = a + u_age * 0.5;
  float seg = fract(ra / 6.2832 * 24.0);
  float glyph = step(0.39, r) * step(r, 0.36 + 0.06) * 0.0;
  float band = step(0.365, r) * step(r, 0.415);
  vec2 gc = floor(vec2(seg * 3.0, (r - 0.365) / 0.05 * 3.0));
  float rune = band * step(0.5, hash(gc + floor(ra / 6.2832 * 24.0) * 5.0)) * step(0.15, seg) * step(seg, 0.85) * drawn;
  float flare = exp(-abs(tl - 2.2) * 3.0);
  vec3 col = mix(vec3(0.35, 0.8, 1.0), vec3(1.0, 0.85, 0.4), 0.5 + 0.5 * sin(u_age + r * 10.0));
  o = over(o, col, exp(-r * 3.0) * 0.25 * drawn + flare * exp(-r * 2.0) * 0.4);
  o = over(o, col, clamp(rings + tri * 0.8 + rune + glyph, 0.0, 1.0));
  for (int i = 0; i < 20; i++) {
    float fi = float(i);
    float life = fract(u_age * (0.2 + 0.2 * hash(vec2(fi, 61.0))) + hash(vec2(fi, 62.0)));
    vec2 m = vec2((hash(vec2(fi, 63.0)) - 0.5) * 1.0, -0.4 + life * 0.9);
    o = over(o, vec3(0.75, 0.9, 1.0), smoothstep(0.008, 0.0, length(c - m)) * (1.0 - life) * drawn);
  }
  o *= smoothstep(7.0, 6.0, tl);
`,
  // sakura storm: a gust carries hundreds of petals across, rays of spring light
  sakurastorm: `
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float aspect = u_res.x / u_res.y;
  float gust = smoothstep(0.0, 0.8, tl) * smoothstep(7.0, 5.5, tl);
  float ray = pow(max(0.0, sin(atan(c.y - 0.6, c.x + 0.6) * 10.0 + u_age * 0.3)), 8.0) * exp(-length(c - vec2(-0.6, 0.6)) * 1.2);
  o = over(o, vec3(1.0, 0.9, 0.85), ray * 0.25 * gust);
  for (int i = 0; i < 40; i++) {
    float fi = float(i);
    float speed = 0.2 + 0.25 * hash(vec2(fi, 71.0));
    float life = fract(u_age * speed + hash(vec2(fi, 72.0)));
    vec2 pos = vec2(-aspect * 0.6 + life * aspect * 1.2, 0.55 - life * 0.6 + (hash(vec2(fi, 73.0)) - 0.5) * 0.9 + 0.08 * sin(life * 8.0 + fi));
    float size = 0.012 + 0.02 * hash(vec2(fi, 74.0));
    float rot = u_age * (1.0 + hash(vec2(fi, 75.0)) * 3.0) + fi;
    vec2 q = mat2(cos(rot), -sin(rot), sin(rot), cos(rot)) * (c - pos) / size;
    q.x /= max(0.3, abs(cos(u_age * 2.0 + fi)));
    float petal = smoothstep(1.0, 0.7, length(q * vec2(1.0, 1.7))) * smoothstep(-0.2, 0.3, q.x + abs(q.y) * 1.2);
    o = over(o, mix(vec3(1.0, 0.75, 0.85), vec3(0.95, 0.5, 0.68), hash(vec2(fi, 76.0))), petal * gust);
  }
`,
  // gold rush: coins rain down tumbling and glinting, a burst of golden light behind
  goldrush: `
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float aspect = u_res.x / u_res.y;
  float glow = exp(-length(c) * 2.5) * smoothstep(0.0, 0.6, tl) * smoothstep(7.0, 5.5, tl);
  float rays = pow(max(0.0, sin(atan(c.y, c.x) * 12.0 + u_age * 0.5)), 6.0) * glow;
  o = over(o, vec3(1.0, 0.78, 0.3), glow * 0.35 + rays * 0.35);
  for (int i = 0; i < 30; i++) {
    float fi = float(i);
    float start = 0.0;
    float life = fract(u_age * (0.22 + 0.15 * hash(vec2(fi, 81.0))) + hash(vec2(fi, 84.0)));
    vec2 pos = vec2((hash(vec2(fi, 82.0)) - 0.5) * aspect + sin(life * 5.0 + fi) * 0.03, 0.62 - life * 1.3);
    float spin = abs(cos(u_age * (2.0 + hash(vec2(fi, 83.0)) * 3.0) + fi));
    vec2 q = (c - pos) / vec2(0.028 * max(spin, 0.12), 0.028);
    float coin = smoothstep(1.0, 0.85, length(q)) * step(start, tl);
    float rim = smoothstep(0.75, 0.95, length(q)) * coin;
    vec3 cc = mix(vec3(0.75, 0.5, 0.1), vec3(1.0, 0.85, 0.35), spin) + vec3(1.0) * smoothstep(0.3, 0.0, length(q - vec2(-0.35, 0.35))) * 0.6;
    o = over(o, mix(cc, vec3(0.55, 0.35, 0.05), rim * 0.6), coin);
  }
  vec2 sg = c * 25.0;
  o = over(o, vec3(1.0, 0.95, 0.7), step(0.985, hash(floor(sg) + floor(u_age * 4.0))) * smoothstep(0.4, 0.0, length(fract(sg) - 0.5)) * glow * 3.0);
`,
  // aurora sky: the night opens — curtains of green and violet light waving, stars, a shooting star
  aurorasky: `
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float show = smoothstep(0.0, 1.5, tl) * smoothstep(7.0, 5.5, tl);
  o = over(o, mix(vec3(0.01, 0.03, 0.08), vec3(0.03, 0.08, 0.2), uv.y), 0.75 * show);
  vec2 sg = c * 40.0;
  o = over(o, vec3(1.0), step(0.985, hash(floor(sg))) * smoothstep(0.4, 0.0, length(fract(sg) - 0.5)) * show * (0.5 + 0.5 * sin(u_age * 3.0 + hash(floor(sg)) * 50.0)));
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float x = c.x * 1.4 + fbm(vec2(c.x * 1.2 + fi * 3.0, u_age * 0.12)) * 1.6;
    float centre = 0.18 + 0.14 * sin(x * 2.2 + u_age * 0.4 + fi * 2.0) + fi * 0.04;
    float curtain = exp(-pow((c.y - centre) * 5.0, 2.0)) * smoothstep(-0.15, centre, c.y) * (0.6 + 0.4 * fbm(vec2(x * 3.0, u_age * 0.2)));
    float rays = 0.65 + 0.35 * sin(c.x * 22.0 + fbm(vec2(c.x * 4.0, u_age * 0.25 + fi)) * 9.0);
    vec3 col = fi < 0.5 ? vec3(0.2, 1.0, 0.55) : fi < 1.5 ? vec3(0.2, 0.85, 0.9) : vec3(0.7, 0.35, 1.0);
    o = over(o, col, curtain * rays * 0.6 * show);
  }
  float st = mod(u_age, 7.0) - 2.0;
  vec2 head = vec2(-0.6 + st * 0.5, 0.45 - st * 0.18);
  vec2 rel = c - head;
  vec2 dir = normalize(vec2(-0.5, 0.18));
  float along = dot(rel, dir);
  float across = abs(dot(rel, vec2(-dir.y, dir.x)));
  o = over(o, vec3(1.0), smoothstep(0.003, 0.0, across) * step(0.0, along) * exp(-along * 10.0) * step(0.0, st) * step(st, 1.2));
`,
  // a time portal: a triangle tearing open behind it (spinning in as it appears, closing as it leaves),
  // its edge crackling with energy, the vortex of time seen through it and inside the shape
  chrono: `
  // once (a notification): the portal opens, then what it brings materialises; as it leaves, it
  // dematerialises first, then the portal closes (its letters follow in CSS: fx-teleport-in / -out)
  float leaving = u_close < 0.0 ? 0.0 : u_close;
  float k = smoothstep(0.0, 0.8, u_age) * (1.0 - smoothstep(0.6, 1.3, leaving));
  float shown = smoothstep(0.8, 1.4, u_age) * (1.0 - smoothstep(0.0, 0.6, leaving));
  float flash = exp(-abs(u_age - 1.0) * 7.0) + (u_close < 0.0 ? 0.0 : exp(-abs(u_close - 0.4) * 7.0));
  if (u_cycle > 0.5) {
    // a teleporter, over and over: the portal opens, the badge materialises, stays, dematerialises, the
    // portal closes — a pause — and again (its letters follow the same cycle in CSS: fx-teleport, 9 s)
    float tc = mod(u_age, 9.0);
    k = smoothstep(0.0, 0.8, tc) * (1.0 - smoothstep(7.1, 7.9, tc));
    shown = smoothstep(0.8, 1.4, tc) * (1.0 - smoothstep(6.5, 7.1, tc));
    flash = exp(-abs(tc - 1.1) * 7.0) + exp(-abs(tc - 6.8) * 7.0);
  }
  float rot = (1.0 - k) * 2.6 + sin(t * 0.6) * 0.05;
  vec2 tp = mat2(cos(rot), -sin(rot), sin(rot), cos(rot)) * (p - vec2(0.0, -0.1));
  float size = (max(ax, 1.0) * 0.9 + 0.75) * max(k, 0.001);
  float tri = sdTri(tp, size);
  float crackle = noise(vec2(atan(tp.y, tp.x) * 6.0, floor(t * 12.0))) * 0.08;
  vec3 seen = vortex(tp / max(size, 0.01) * 1.4, t);
  o = over(o, seen, smoothstep(0.02, -0.04, tri) * 0.92 * k);
  o = over(o, vec3(0.4, 0.75, 1.0), exp(-abs(tri - crackle) * 14.0) * k);
  o = over(o, vec3(1.0, 0.95, 0.8), exp(-abs(tri) * 45.0) * k);
  o = over(o, vec3(0.8, 0.9, 1.0), flash * exp(-length(p) * 1.5) * 0.7);
  for (int i = 0; i < 8; i++) {
    float fi = float(i);
    float life = fract(t * (0.4 + 0.3 * hash(vec2(fi, 91.0))) + hash(vec2(fi, 92.0)));
    float ang = hash(vec2(fi, 93.0)) * 6.2832 + life * 2.0;
    vec2 sp = vec2(cos(ang), sin(ang)) * size * (1.3 - life * 1.2);
    o = over(o, vec3(1.0, 0.85, 0.5), smoothstep(0.06, 0.0, length(tp - sp)) * (1.0 - life) * k);
  }
  vec3 body = vortex(p * 0.8, t) * 0.75;
  body += vec3(0.5, 0.8, 1.0) * smoothstep(-0.15, 0.0, d) * 0.6;
  o = over(o, body, smoothstep(0.03, -0.03, d) * shown);
`,
  // the time portal, full stage: its three sides draw one after another, it tears open, pulls everything
  // in, flashes — and closes again
  timeportal: `
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float k = smoothstep(0.9, 1.6, tl) * smoothstep(6.6, 5.6, tl);
  float rot = (1.0 - k) * 3.0 + u_age * 0.05;
  vec2 tp = mat2(cos(rot), -sin(rot), sin(rot), cos(rot)) * c;
  float size = 0.42 * max(k, 0.0) + 0.0001;
  float tri = sdTri(tp, size);
  o = over(o, vortex(tp / max(size, 0.01) * 1.3, u_age), smoothstep(0.004, -0.01, tri) * 0.95 * k);
  float drawn = smoothstep(0.0, 1.0, tl);
  vec2 q = tp;
  float side = 0.0;
  for (int i = 0; i < 3; i++) {
    float a = float(i) * 2.0944;
    vec2 v = mat2(cos(a), -sin(a), sin(a), cos(a)) * q;
    float along = (v.x / 0.36 + 0.5);
    float reveal = step(along, clamp(drawn * 3.0 - float(i), 0.0, 1.0));
    side += exp(-abs(v.y + 0.42 * 0.577) * 220.0) * step(0.0, along) * step(along, 1.0) * reveal * (1.0 - k);
  }
  o = over(o, vec3(0.6, 0.85, 1.0), clamp(side, 0.0, 1.0));
  float crackle = noise(vec2(atan(tp.y, tp.x) * 8.0, floor(u_age * 14.0))) * 0.015;
  o = over(o, vec3(0.4, 0.75, 1.0), exp(-abs(tri - crackle) * 60.0) * k);
  o = over(o, vec3(1.0, 0.95, 0.85), exp(-abs(tri) * 200.0) * k);
  float flash = exp(-abs(tl - 1.6) * 8.0) + exp(-abs(tl - 6.4) * 8.0);
  o = over(o, vec3(0.85, 0.92, 1.0), flash * exp(-length(c) * 1.5) * 0.8);
  for (int i = 0; i < 40; i++) {
    float fi = float(i);
    float life = fract(u_age * (0.25 + 0.25 * hash(vec2(fi, 94.0))) + hash(vec2(fi, 95.0)));
    float ang = hash(vec2(fi, 96.0)) * 6.2832 + life * 3.0;
    vec2 sp = vec2(cos(ang), sin(ang)) * (1.0 - life) * 0.9;
    o = over(o, mix(vec3(1.0, 0.85, 0.5), vec3(0.6, 0.85, 1.0), hash(vec2(fi, 97.0))), smoothstep(0.008, 0.0, length(c - sp)) * life * k);
  }
`,
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
  effect: FxBadge;
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

/** « burst:blaze » plays the flames of « blaze » as a burst (a notification's entrance and exit) */
function baseOf(effect: string): FxBadge {
  return (effect.startsWith("burst:") ? effect.slice(6) : effect) as FxBadge;
}

/** The fragment shader an effect is drawn with (also read by tests and previews). */
export function fxFragment(effect: string): string {
  const base = baseOf(effect);
  // issue 1: an imported pack's look, in the same frame as the built-in ones
  const external = externalFx(base);
  const body = external ? external.body : EFFECTS[base];
  return `${HEAD}${MAIN_OPEN}${body}${stageOf(base) ? CLOSE_FULL : CLOSE}`;
}

function stageOf(effect: string): boolean {
  return FULL_STAGE.has(effect) || Boolean(externalFx(effect)?.stage);
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
  const burst = instance.effect.startsWith("burst:") && baseOf(instance.effect) !== "chrono";
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
  const live = frozen ? new Set<Instance>() : moving(visible, liveLooks());
  for (const instance of visible) {
    if (instance.drawn && !live.has(instance)) continue;
    if (!draw(context, instance, time)) instance.host.dataset.fxFailed = "true";
    instance.drawn = true;
  }
}

export function attachFx(
  canvas: HTMLCanvasElement,
  host: HTMLElement,
  effect: FxBadge,
  options: FxOptions = {},
): (() => void) | null {
  if (!(FX_EFFECTS as readonly string[]).includes(baseOf(effect)) && !externalFx(baseOf(effect))) return null;
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
