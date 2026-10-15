import { SAFE_COMMON } from "./weatherShader";

/**
 * issue 130: the « Cosmos » ambiences drawn by the GPU — behind the whole portal or in a profile's banner.
 * Premultiplied over the page like the others, light enough to read through, kept to GLSL ES 1.0 and to
 * the noise that stays sound on phones of lower precision (``SAFE_COMMON``).
 */

const STARS = `
float fbm4(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  mat2 turn = mat2(0.8, 0.6, -0.6, 0.8);
  for (int i = 0; i < 4; i++) {
    v += a * noise(p);
    p = turn * p * 2.03 + vec2(1.7, 9.2);
    a *= 0.5;
  }
  return v;
}
// thin bright filaments: the creases of a noise, sharpened octave after octave
float ridged(vec2 p) {
  float v = 0.0;
  float a = 0.55;
  float prev = 1.0;
  mat2 turn = mat2(0.8, 0.6, -0.6, 0.8);
  for (int i = 0; i < 5; i++) {
    float n = 1.0 - abs(2.0 * noise(p) - 1.0);
    n = n * n;
    v += n * a * prev;
    prev = n;
    p = turn * p * 2.1 + vec2(3.1, 7.7);
    a *= 0.5;
  }
  return v;
}
float starfield(vec2 p, float scale, float t, float density) {
  vec2 sg = p * scale;
  vec2 id = floor(sg);
  float h = hash(id);
  vec2 at = vec2(hash(id + 3.1), hash(id + 7.7)) - 0.5;
  float s = step(1.0 - density, h) * smoothstep(0.12 + 0.1 * hash(id + 1.3), 0.0, length(fract(sg) - 0.5 - at * 0.6));
  return s * (0.55 + 0.45 * sin(t * (1.0 + 2.0 * hash(id + 5.0)) + h * 40.0));
}
// a star seen by a great telescope: a bright core, a halo and six diffraction spikes (two short ones across)
float spiked(vec2 d, float size) {
  float r = length(d);
  float core = exp(-r / size * 3.2) + exp(-r / size * 0.9) * 0.18;
  float spikes = 0.0;
  for (int i = 0; i < 3; i++) {
    float a = float(i) * 1.0472 + 1.5708;
    vec2 dir = vec2(cos(a), sin(a));
    float along = abs(dot(d, dir));
    float across = abs(dot(d, vec2(-dir.y, dir.x)));
    spikes += exp(-across / size * 9.0) * exp(-along / size * 0.55);
  }
  spikes += 0.5 * exp(-abs(d.y) / size * 9.0) * exp(-abs(d.x) / size * 1.1);
  return core + spikes * 0.55;
}
// a few big stars with their spikes, slowly twinkling, coloured blue-white to gold
vec4 brightStars(vec4 o, vec2 p, float aspect, float t, float seed, float count) {
  for (int i = 0; i < 7; i++) {
    float fi = float(i);
    if (fi >= count) break;
    vec2 at = vec2(hash(vec2(fi, seed)) * aspect, 0.08 + hash(vec2(fi, seed + 1.0)) * 0.86);
    float size = 0.006 + 0.008 * hash(vec2(fi, seed + 2.0));
    float tw = 0.75 + 0.25 * sin(t * (0.7 + hash(vec2(fi, seed + 3.0))) + fi * 2.0);
    vec3 col = mix(vec3(0.75, 0.85, 1.0), vec3(1.0, 0.88, 0.7), hash(vec2(fi, seed + 4.0)));
    o = over(o, col, clamp(spiked(p - at, size) * tw, 0.0, 1.0));
  }
  return o;
}
`;

/** M42, the great Orion nebula: billowing clouds of magenta and crimson round a white-hot heart where the
 * Trapezium's young stars blaze, violet and blue wings spreading out, dark bays of dust, the little round
 * puff of M43 beside it; the gas folding slowly on itself, the stars twinkling. */
const ORION = `${SAFE_COMMON}${STARS}
// from the white-hot heart outwards: pink, crimson, magenta, violet, then the blue of the wings
vec3 orionColour(float x) {
  vec3 c = mix(vec3(1.0, 0.95, 0.97), vec3(1.0, 0.55, 0.75), smoothstep(0.0, 0.15, x));
  c = mix(c, vec3(0.97, 0.18, 0.4), smoothstep(0.12, 0.35, x));
  c = mix(c, vec3(0.75, 0.15, 0.6), smoothstep(0.35, 0.6, x));
  c = mix(c, vec3(0.38, 0.2, 0.7), smoothstep(0.55, 0.8, x));
  return mix(c, vec3(0.22, 0.35, 0.9), smoothstep(0.78, 1.0, x));
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);
  float aspect = u_res.x / u_res.y;
  vec2 q = (p - vec2(0.55 * aspect, 0.46)) * 1.25;
  vec2 w1 = vec2(fbm4(q * 1.1 + vec2(t * 0.014, 0.0)), fbm4(q * 1.1 + vec2(5.2, 1.3) - t * 0.011));
  vec2 w2 = vec2(fbm4(q * 1.9 + w1 * 2.2 + vec2(1.7, 9.2)), fbm4(q * 1.9 + w1 * 2.2 + vec2(8.3, 2.8) + t * 0.012));
  vec2 at = q * 1.5 + w2 * 2.4;
  float n = fbm(at);
  // the billows lit from the heart: brighter where the cloud rises towards it
  vec2 toHeart = normalize(vec2(-0.08, 0.2) - q + 1e-4);
  float lift = (fbm(at + toHeart * 0.06) - n) * 14.0;
  float r = length(q * vec2(0.82, 1.0));
  float envelope = smoothstep(1.25, 0.25, r + (w1.x - 0.5) * 0.7);
  float density = smoothstep(0.28, 0.66, n) * envelope;
  float core = length(q - vec2(-0.08, 0.2));
  vec3 col = orionColour(clamp(core * 0.85 + (0.62 - n) * 0.7 + (w2.y - 0.5) * 0.3, 0.0, 1.0));
  col *= 0.85 + 0.65 * clamp(0.5 + lift, 0.0, 1.0);
  float fil = ridged(q * 2.4 + w2 * 1.7 + vec2(0.0, t * 0.005));
  col += vec3(1.0, 0.7, 0.85) * pow(fil, 3.0) * 0.4 * density;
  float dust = smoothstep(0.6, 0.8, fbm4(q * 3.2 - w1 * 2.0 + 3.0)) * smoothstep(0.15, 0.8, core);
  float a = clamp(density * (0.65 + 0.45 * n) + exp(-core * 3.5) * 0.6, 0.0, 0.95) * (1.0 - dust * 0.85);
  vec4 o = vec4(col * a, a);
  vec2 m = q - vec2(-0.6, 0.66);
  float puff = smoothstep(0.26, 0.0, length(m) + (fbm4(m * 6.0 + t * 0.01) - 0.5) * 0.14);
  o = over(o, orionColour(clamp(length(m) * 3.0, 0.0, 0.6)), puff * 0.65);
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    vec2 s = q - vec2(-0.12 + 0.07 * mod(fi, 2.0), 0.18 + 0.06 * floor(fi / 2.0) + 0.012 * fi);
    float tw = 0.85 + 0.15 * sin(t * (2.0 + fi) + fi);
    o = over(o, vec3(0.88, 0.94, 1.0), clamp(spiked(s, 0.011) * tw, 0.0, 1.0));
  }
  o = over(o, vec3(1.0, 0.96, 0.92), starfield(p, 75.0, t, 0.03) * (1.0 - density * 0.6));
  o = over(o, vec3(0.75, 0.82, 1.0), starfield(p + 3.0, 150.0, t, 0.025) * 0.6 * (1.0 - density * 0.5));
  o = brightStars(o, p, aspect, t, 11.0, 4.0);
  gl_FragColor = o;
}`;

/** M1, the Crab: what a star left when it blew up — a web of orange and red filaments, yellow-green in
 * places, round a ghostly cyan glow; its pulsar flickering in the middle, the whole cloud breathing out
 * slowly. */
const CRAB = `${SAFE_COMMON}${STARS}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);
  float aspect = u_res.x / u_res.y;
  float grow = 1.0 + 0.035 * sin(t * 0.07);
  vec2 q = (p - vec2(0.55 * aspect, 0.5)) * 2.0 / grow;
  q = mat2(0.9, -0.44, 0.44, 0.9) * q;
  vec2 w = vec2(fbm4(q * 1.4 + vec2(t * 0.01, 2.0)), fbm4(q * 1.4 + vec2(6.0, -t * 0.008)));
  float r = length(q * vec2(0.74, 1.0)) + (w.x - 0.5) * 0.3 + (fbm4(q * 3.0) - 0.5) * 0.15;
  float m = smoothstep(1.02, 0.82, r);
  float glow = fbm(q * 2.0 + w * 1.6 + vec2(0.0, t * 0.006));
  vec4 o = vec4(0.0);
  vec3 cyan = mix(vec3(0.12, 0.5, 0.8), vec3(0.5, 0.95, 1.0), glow);
  o = over(o, cyan, m * exp(-r * r * 2.6) * (0.25 + 0.55 * glow));
  // the web: a dense net of fine filaments, and a few thicker strands
  float fine = smoothstep(0.3, 0.62, ridged(q * 4.5 + w * 2.6 + vec2(t * 0.003, 0.0)));
  float strands = smoothstep(0.42, 0.75, ridged(q * 2.2 + w * 1.6 + 4.0));
  vec3 fcol = mix(vec3(1.0, 0.85, 0.55), vec3(1.0, 0.45, 0.12), smoothstep(0.15, 0.6, r));
  fcol = mix(fcol, vec3(0.9, 0.12, 0.06), smoothstep(0.55, 0.95, r));
  fcol = mix(fcol, vec3(0.6, 0.85, 0.3), smoothstep(0.62, 0.9, w.y) * smoothstep(0.3, 0.7, r) * 0.7);
  float reach = 0.35 + 0.65 * smoothstep(0.1, 0.8, r);
  float lace = smoothstep(0.32, 0.6, ridged(q * 9.0 + w * 3.0 + 7.0));
  o = over(o, fcol, clamp(fine * 0.6 + strands * 0.6 + lace * 0.35, 0.0, 1.0) * m * reach);
  o = over(o, vec3(0.95, 0.3, 0.15), smoothstep(1.1, 0.75, r) * smoothstep(0.75, 0.95, r) * fbm4(q * 4.0 - w) * 0.35);
  float pulse = 0.55 + 0.45 * step(0.5, fract(t * 1.5));
  o = over(o, vec3(0.85, 0.95, 1.0), clamp(spiked(p - vec2(0.55 * aspect, 0.5), 0.004) * pulse, 0.0, 1.0));
  o = over(o, vec3(0.75, 0.9, 1.0), starfield(p, 80.0, t, 0.035) * (1.0 - m * 0.6));
  o = over(o, vec3(1.0, 0.9, 0.8), starfield(p + 5.0, 150.0, t, 0.02) * 0.5);
  o = brightStars(o, p, aspect, t, 23.0, 3.0);
  gl_FragColor = o;
}`;

/** The Helix — the « eye of God »: a ring of teal gas streaked outward with cometary knots, a red and
 * orange inner ring, a deep blue heart with its dying white star; turning slowly, breathing. */
const HELIX = `${SAFE_COMMON}${STARS}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);
  float aspect = u_res.x / u_res.y;
  vec2 q = (p - vec2(0.55 * aspect, 0.5)) * 1.7;
  float turn = t * 0.01;
  q = mat2(cos(turn), -sin(turn), sin(turn), cos(turn)) * q;
  q.x *= 0.88;
  float r = length(q) * (1.0 + 0.015 * sin(t * 0.3));
  float ang = atan(q.y, q.x);
  vec2 polar = vec2(ang * 3.0, r * 2.0);
  float wob = (fbm4(vec2(cos(ang), sin(ang)) * 2.0 + t * 0.01) - 0.5) * 0.18;
  vec4 o = vec4(0.0);
  float heart = exp(-r * r * 9.0);
  o = over(o, mix(vec3(0.1, 0.25, 0.75), vec3(0.4, 0.6, 1.0), heart), heart * 0.55);
  float inner = exp(-pow((r - 0.42 - wob) / 0.13, 2.0));
  float ripple = fbm(vec2(cos(ang), sin(ang)) * 3.0 + vec2(r * 4.0, t * 0.01));
  o = over(o, mix(vec3(0.9, 0.15, 0.1), vec3(1.0, 0.55, 0.15), ripple), inner * (0.45 + 0.45 * ripple));
  float outer = exp(-pow((r - 0.72 - wob * 1.3) / 0.24, 2.0));
  float rays = fbm4(vec2(ang * 9.0 / 6.2832 * 6.0, r * 1.5 - t * 0.01)) * 0.6 + 0.4 * fbm(vec2(cos(ang), sin(ang)) * 5.0 + r * 2.0);
  vec3 teal = mix(vec3(0.05, 0.45, 0.5), vec3(0.4, 0.95, 0.85), rays);
  o = over(o, teal, outer * (0.3 + 0.55 * rays));
  // cometary knots on the ring's inner edge, their tails pointing out
  vec2 kg = vec2(ang / 6.2832 * 70.0, (r - 0.55) * 22.0);
  vec2 kid = floor(kg);
  vec2 kf = fract(kg) - vec2(0.5, 0.2);
  float knot = step(0.55, hash(kid)) * step(abs(r - 0.6 - wob), 0.15) * smoothstep(0.18, 0.0, abs(kf.x)) * smoothstep(0.7, -0.1, kf.y) * step(-0.2, kf.y);
  o = over(o, vec3(0.75, 1.0, 0.95), knot * 0.5);
  float halo = exp(-pow((r - 1.05) / 0.25, 2.0)) * fbm4(polar + t * 0.005);
  o = over(o, vec3(0.6, 0.25, 0.2), halo * 0.3);
  o = over(o, vec3(1.0), clamp(spiked(q / 1.7, 0.005), 0.0, 1.0));
  o = over(o, vec3(0.85, 0.92, 1.0), starfield(p, 80.0, t, 0.035));
  o = over(o, vec3(1.0, 0.9, 0.85), starfield(p + 2.0, 160.0, t, 0.025) * 0.5);
  o = brightStars(o, p, aspect, t, 31.0, 3.0);
  gl_FragColor = o;
}`;

/** The Pillars of Creation, as the newest telescope saw them: towering columns of golden-brown dust rising
 * against a deep blue field of stars, their tops lit and evaporating, a red glow where stars are being born
 * inside, wisps flowing off them; big stars with their six spikes. */
const PILLARS = `${SAFE_COMMON}${STARS}
// a column of dust, leaning, lumpy, wide at its foot, its head swollen — a signed distance (< 0 inside)
float column(vec2 p, vec2 base, float top, float wid, float lean, float seed) {
  float h = max(top - base.y, 0.01);
  float y = clamp((p.y - base.y) / h, 0.0, 1.2);
  float x = p.x - base.x - lean * (p.y - base.y) - 0.04 * sin(y * 4.0 + seed);
  float w = wid * (1.6 - 0.9 * smoothstep(0.0, 1.0, y)) * (1.0 + 0.55 * (fbm4(vec2(p.y * 4.5, seed)) - 0.5));
  w += wid * 0.5 * smoothstep(0.08, 0.0, abs(y - 0.35 - 0.2 * hash(vec2(seed, 2.0)))) * step(0.0, x * sign(hash(vec2(seed, 3.0)) - 0.5));
  float side = abs(x) - w;
  vec2 hp = vec2(p.x - base.x - lean * h - 0.04 * sin(4.0 + seed), p.y - top);
  float head = length(hp * vec2(1.0, 1.15)) - wid * 0.95;
  float d = min(max(side, p.y - top), head);
  return d + (fbm(p * 12.0 + seed) - 0.5) * 0.05 + (fbm4(p * 5.0 + seed) - 0.5) * 0.06 + (noise(p * 40.0) - 0.5) * 0.012;
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);
  float aspect = u_res.x / u_res.y;
  vec2 w = vec2(fbm4(p * 1.6 + vec2(t * 0.008, 0.0)), fbm4(p * 1.6 + vec2(3.0, t * 0.006)));
  float field = fbm(p * 1.3 + w * 1.4);
  vec3 sky = mix(vec3(0.03, 0.07, 0.26), vec3(0.14, 0.32, 0.68), smoothstep(0.35, 0.85, field));
  sky = mix(sky, vec3(0.28, 0.55, 0.75), smoothstep(0.7, 0.95, field) * 0.4);
  float a = 0.32 + 0.25 * field;
  vec4 o = vec4(sky * a, a);
  o = over(o, vec3(1.0, 0.97, 0.9), starfield(p, 85.0, t, 0.045));
  o = over(o, vec3(0.8, 0.88, 1.0), starfield(p + 9.0, 170.0, t, 0.04) * 0.7);
  float x0 = 0.16 * aspect;
  float d1 = column(p, vec2(x0, -0.12), 0.8, 0.075, 0.32, 1.0);
  float d2 = column(p, vec2(x0 + 0.3 * aspect, -0.12), 0.58, 0.06, 0.28, 4.0);
  float d3 = column(p, vec2(x0 + 0.56 * aspect, -0.12), 0.36, 0.05, 0.2, 7.0);
  float d = min(d1, min(d2, d3));
  float body = smoothstep(0.012, -0.012, d);
  float depth = clamp(-d * 7.0, 0.0, 1.0);
  float fluff = fbm(p * 7.0 + w * 2.0);
  float grain = fbm(p * 20.0 + w * 2.0);
  vec3 dust = mix(vec3(0.58, 0.34, 0.13), vec3(0.2, 0.09, 0.04), depth);
  dust = mix(dust, vec3(0.86, 0.62, 0.3), smoothstep(0.55, 0.85, fluff) * (1.0 - depth) * 0.6);
  dust *= 0.6 + 0.5 * grain * fluff + 0.15;
  // lit from above right: the edges facing the light glow gold, the others stay dark
  vec2 eps = vec2(0.01, 0.0);
  vec2 normal = normalize(vec2(min(column(p + eps.xy, vec2(x0, -0.12), 0.8, 0.075, 0.32, 1.0), d) - d + 1e-4, 0.01));
  float facing = smoothstep(-0.2, 0.8, dot(normalize(vec2(0.6, 0.8)), vec2(1.0, 0.6) * sign(p.x - x0 - 0.32 * (p.y + 0.12))));
  float rim = smoothstep(0.035, 0.0, abs(d)) * (0.35 + 0.65 * facing);
  o = over(o, dust, body * 0.96);
  o = over(o, vec3(1.0, 0.8, 0.48), rim * 0.6);
  vec2 tip1 = vec2(x0 + 0.32 * 0.92 + 0.04 * sin(5.0), 0.8);
  vec2 tip2 = vec2(x0 + 0.3 * aspect + 0.28 * 0.7 + 0.04 * sin(8.0), 0.58);
  float tops = exp(-length((p - tip1) * vec2(1.0, 1.6)) * 16.0) + exp(-length((p - tip2) * vec2(1.0, 1.6)) * 20.0);
  o = over(o, vec3(1.0, 0.32, 0.28), tops * (0.5 + 0.15 * sin(t * 0.7)));
  for (int i = 0; i < 2; i++) {
    vec2 tip = i == 0 ? tip1 : tip2;
    vec2 v = p - tip;
    float plume = fbm4(vec2(v.x * 8.0 - t * 0.03, v.y * 5.0 - t * 0.12)) * smoothstep(0.26, 0.0, length(v * vec2(1.2, 0.75))) * step(-0.03, v.y);
    o = over(o, vec3(0.9, 0.78, 0.6), smoothstep(0.35, 0.7, plume) * 0.5);
  }
  o = brightStars(o, p, aspect, t, 41.0, 6.0);
  gl_FragColor = o;
}`;

/** The « cosmic cliffs » of Carina: a ridge of orange-brown dust running along the bottom like a mountain
 * range, steam rising from its crest into a blue sky of glowing gas, stars with their spikes. */
const CLIFFS = `${SAFE_COMMON}${STARS}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);
  float aspect = u_res.x / u_res.y;
  vec2 w = vec2(fbm4(p * 1.4 + vec2(t * 0.006, 0.0)), fbm4(p * 1.4 + vec2(4.0, -t * 0.005)));
  float gas = fbm(p * 1.8 + w * 1.6 + vec2(0.0, -t * 0.004));
  vec3 sky = mix(vec3(0.04, 0.1, 0.3), vec3(0.25, 0.5, 0.88), smoothstep(0.35, 0.85, gas));
  sky = mix(sky, vec3(0.6, 0.85, 0.95), smoothstep(0.75, 0.95, gas) * 0.35);
  float a = (0.3 + 0.3 * gas) * smoothstep(0.15, 0.55, uv.y);
  vec4 o = vec4(sky * a, a);
  o = over(o, vec3(1.0, 0.97, 0.9), starfield(p, 85.0, t, 0.045) * smoothstep(0.3, 0.55, uv.y));
  // a mountain range of dust: big swells, crags, a few spires
  float x = p.x;
  float crest = 0.22 + 0.22 * fbm4(vec2(x * 1.1, 1.0)) + 0.06 * fbm4(vec2(x * 3.5, 3.0)) + 0.025 * fbm(vec2(x * 18.0, 5.0));
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float sx = (0.2 + 0.3 * fi + 0.08 * hash(vec2(fi, 4.0))) * aspect;
    crest += (0.06 + 0.06 * hash(vec2(fi, 5.0))) * exp(-pow((x - sx) / (0.09 + 0.06 * hash(vec2(fi, 6.0))), 2.0));
  }
  float d = uv.y - crest + (fbm(vec2(x * 22.0, p.y * 22.0) + w) - 0.5) * 0.035;
  float cliff = smoothstep(0.006, -0.006, d);
  float depth = clamp(-d * 4.0, 0.0, 1.0);
  float fluff = fbm(vec2(x * 6.0, p.y * 7.0) + w * 1.5);
  float grain = fbm(vec2(x * 16.0, p.y * 18.0) + w);
  vec3 rock = mix(vec3(0.85, 0.52, 0.26), vec3(0.26, 0.11, 0.05), depth);
  rock = mix(rock, vec3(0.98, 0.74, 0.44), smoothstep(0.55, 0.85, fluff) * (1.0 - depth * 0.8) * 0.6);
  rock *= 0.6 + 0.35 * grain + 0.2 * fluff;
  o = over(o, rock, cliff * 0.96);
  o = over(o, vec3(1.0, 0.82, 0.55), smoothstep(0.03, 0.0, abs(d)) * 0.55);
  float steam = fbm4(vec2(x * 5.0 + w.x * 1.5, d * 4.0 - t * 0.07)) * smoothstep(-0.01, 0.03, d) * smoothstep(0.3, 0.0, d);
  o = over(o, vec3(0.88, 0.82, 0.78), smoothstep(0.38, 0.75, steam) * 0.5);
  o = brightStars(o, p, aspect, t, 53.0, 6.0);
  gl_FragColor = o;
}`;

/** The solar system seen at a slant: the sun glowing on the left, six planets on their tilted orbits — the
 * nearest quick, the farthest slow — the asteroid belt, a ringed giant, the orbits drawn faintly. */
const SOLARSYSTEM = `${SAFE_COMMON}${STARS}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, vec3(1.0, 0.97, 0.9), starfield(p, 90.0, t, 0.025));
  vec2 sun = vec2(0.32 * aspect, 0.46);
  vec2 q = (p - sun) * vec2(1.0, 2.6);
  float rs = length(p - sun);
  o = over(o, vec3(1.0, 0.6, 0.2), exp(-rs * 6.0) * 0.5);
  o = over(o, vec3(1.0, 0.85, 0.5), exp(-rs * 18.0) * (0.9 + 0.1 * sin(t * 2.0)));
  o = over(o, vec3(1.0, 0.97, 0.85), smoothstep(0.045, 0.035, rs));
  // the belt, between the fourth and the fifth orbit
  float rq = length(q);
  float belt = smoothstep(0.03, 0.0, abs(rq - 0.6)) * step(0.985, hash(floor(vec2(atan(q.y, q.x) * 120.0 + t * 0.6, rq * 140.0))));
  o = over(o, vec3(0.75, 0.7, 0.65), belt * 0.7);
  for (int i = 0; i < 6; i++) {
    float fi = float(i);
    float rad = 0.16 + 0.11 * fi + (fi > 3.5 ? 0.08 : 0.0);
    o = over(o, vec3(0.5, 0.6, 0.9), smoothstep(0.004, 0.0, abs(rq - rad)) * 0.18);
    float a = t * 0.6 / pow(rad * 4.0, 1.5) + fi * 2.1;
    vec2 at = sun + vec2(cos(a), sin(a) / 2.6) * rad;
    float size = 0.012 + 0.006 * mod(fi * 5.0, 3.0) + (fi > 3.5 ? 0.012 : 0.0);
    vec2 d = p - at;
    float dp = length(d);
    vec3 hue = fi < 0.5 ? vec3(0.7, 0.65, 0.6) : fi < 1.5 ? vec3(0.95, 0.8, 0.5) : fi < 2.5 ? vec3(0.3, 0.55, 1.0)
      : fi < 3.5 ? vec3(0.9, 0.4, 0.25) : fi < 4.5 ? vec3(0.9, 0.75, 0.55) : vec3(0.85, 0.8, 0.6);
    float lit = 0.3 + 0.7 * smoothstep(-0.5, 0.9, dot(normalize(sun - at), d / max(dp, 1e-4)));
    float behind = step(0.0, sin(a));  // the far side of the orbit: dimmer, smaller
    float body = smoothstep(size, size * 0.8, dp);
    if (fi > 4.5) {
      vec2 rq2 = d / vec2(size * 2.4, size * 0.7);
      float ring = smoothstep(1.0, 0.95, length(rq2)) * smoothstep(0.62, 0.68, length(rq2));
      o = over(o, vec3(0.9, 0.85, 0.7), ring * 0.8);
    }
    o = over(o, hue * lit * (1.0 - 0.25 * behind), body);
    o = over(o, hue, exp(-max(dp - size, 0.0) * 60.0) * 0.2);
  }
  gl_FragColor = o;
}`;

/** A ringed giant rising in a corner: its banded clouds turning, a storm, its rings with their gap, the
 * shadow they cast, little moons going round; stars behind. */
const SATURNRISE = `${SAFE_COMMON}${STARS}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, vec3(1.0, 0.97, 0.9), starfield(p, 90.0, t, 0.03));
  vec2 ctr = vec2(0.8 * aspect, -0.05);
  float R = 0.55;
  vec2 c = p - ctr;
  float tilt = -0.28;
  vec2 q = mat2(cos(tilt), -sin(tilt), sin(tilt), cos(tilt)) * c;
  float r = length(c);
  float lat = q.y / R;
  float bands = sin(lat * 18.0 + fbm(vec2(q.x * 2.5 - t * 0.02, lat * 5.0)) * 2.5);
  vec3 planet = mix(vec3(0.72, 0.55, 0.35), vec3(0.97, 0.88, 0.68), 0.5 + 0.5 * bands);
  planet = mix(planet, vec3(0.6, 0.4, 0.25), smoothstep(0.55, 0.85, fbm(vec2(q.x * 4.0 - t * 0.03, lat * 12.0))) * 0.4);
  float z = sqrt(max(0.0, 1.0 - dot(c, c) / (R * R)));
  vec3 n = vec3(c / R, z);
  float light = clamp(dot(n, normalize(vec3(-0.7, 0.5, 0.5))), 0.0, 1.0);
  planet *= 0.12 + 0.95 * light;
  vec2 rq = vec2(q.x, q.y * 4.6) / R;
  float rr = length(rq);
  float ring = smoothstep(1.25, 1.28, rr) * smoothstep(2.25, 2.2, rr);
  ring *= 0.55 + 0.45 * sin(rr * 45.0) * sin(rr * 11.0 + 1.0);
  ring *= 1.0 - 0.9 * smoothstep(1.8, 1.83, rr) * smoothstep(1.9, 1.87, rr);
  vec3 rcol = mix(vec3(0.75, 0.68, 0.55), vec3(1.0, 0.95, 0.85), smoothstep(1.3, 2.2, rr)) * (0.45 + 0.55 * smoothstep(-0.6, 0.4, -q.x / R));
  float inside = smoothstep(R + 0.004, R - 0.004, r);
  float front = step(q.y, 0.0);
  float shadow = smoothstep(0.03, 0.0, abs(q.y - 0.06)) * 0.0 + smoothstep(R * 0.24, R * 0.16, abs(q.y + 0.02 - q.x * 0.0)) * step(0.0, q.x) * 0.35;
  o = over(o, vec3(0.95, 0.8, 0.55), exp(-max(r - R, 0.0) * 9.0) * 0.18 * step(R, r));
  o = over(o, rcol, ring * (1.0 - front) * (1.0 - inside) * 0.9);
  o = over(o, planet * (1.0 - shadow), inside);
  o = over(o, rcol, ring * front * 0.92);
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float a = t * (0.08 + 0.05 * fi) + fi * 2.0;
    vec2 at = ctr + mat2(cos(tilt), sin(tilt), -sin(tilt), cos(tilt)) * vec2(cos(a) * R * (2.5 + 0.5 * fi), sin(a) * R * (2.5 + 0.5 * fi) / 4.6);
    float hidden = step(0.0, sin(a)) * inside;
    o = over(o, vec3(0.85, 0.85, 0.9), smoothstep(0.012, 0.008, length(p - at)) * (1.0 - hidden));
  }
  gl_FragColor = o;
}`;

/** The Perseids: a summer night over the hills, the shooting stars streaking from their radiant up high,
 * now and then a fireball; the Milky Way faint behind. */
const PERSEIDS = `${SAFE_COMMON}${STARS}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  float band = exp(-abs(uv.y - 0.6 - (uv.x - 0.5) * 0.4) * 5.0) * fbm(p * 3.0);
  o = over(o, vec3(0.55, 0.6, 0.85), band * 0.18);
  o = over(o, vec3(1.0, 0.97, 0.9), starfield(p, 90.0, t, 0.035) * smoothstep(0.1, 0.3, uv.y));
  vec2 radiant = vec2(0.8 * aspect, 0.95);
  for (int i = 0; i < 14; i++) {
    float fi = float(i);
    float period = 2.6 + 2.5 * hash(vec2(fi, 1.0));
    float k = floor((t + fi * 1.7) / period);
    float life = fract((t + fi * 1.7) / period) * period / 0.9;
    if (life > 1.3 || hash(vec2(k, fi + 9.0)) < 0.2) continue;
    float a = 3.4 + hash(vec2(k, fi + 2.0)) * 1.4;
    vec2 way = vec2(cos(a), sin(a));
    vec2 head = radiant + way * (0.15 + 0.4 * hash(vec2(k, fi + 3.0)) + life * 0.9);
    vec2 rel = p - head;
    float along = dot(rel, -way);
    float across = abs(dot(rel, vec2(-way.y, way.x)));
    float big = step(0.9, hash(vec2(k, fi + 4.0)));
    float trail = smoothstep(mix(0.0018, 0.004, big), 0.0, across) * smoothstep(0.3 + big * 0.2, 0.0, along) * step(0.0, along);
    float burn = smoothstep(0.0, 0.15, life) * smoothstep(1.3, 0.8, life);
    vec3 col = mix(vec3(0.8, 0.88, 1.0), vec3(0.6, 1.0, 0.7), big);
    o = over(o, col, trail * burn);
    o = over(o, vec3(1.0), exp(-length(rel) * mix(250.0, 90.0, big)) * burn);
  }
  // rolling hills against the sky, a nearer darker ridge
  float far = 0.16 + 0.05 * sin(p.x * 2.3 + 1.0) + 0.04 * fbm4(vec2(p.x * 3.0, 1.0));
  float near = 0.08 + 0.04 * sin(p.x * 4.1 + 2.0) + 0.03 * fbm4(vec2(p.x * 6.0, 4.0));
  o = over(o, vec3(0.04, 0.05, 0.1), smoothstep(0.004, 0.0, uv.y - far) * 0.85);
  o = over(o, vec3(0.015, 0.02, 0.04), smoothstep(0.004, 0.0, uv.y - near) * 0.95);
  gl_FragColor = o;
}`;

/** Constellations drawing themselves in turn — Orion, Cassiopeia, the Plough, the Swan, the Lion, the
 * Scorpion — star after star then line after line, shining, fading; the sky turning slowly behind. */
const CONSTELLATIONS = `${SAFE_COMMON}${STARS}
vec2 cstar(float k, float i) {
  if (k < 0.5) { // Orion
    if (i < 0.5) return vec2(-0.35, 0.45); if (i < 1.5) return vec2(0.3, 0.4); if (i < 2.5) return vec2(-0.08, 0.0);
    if (i < 3.5) return vec2(0.0, 0.03); if (i < 4.5) return vec2(0.08, 0.06); if (i < 5.5) return vec2(-0.28, -0.45);
    if (i < 6.5) return vec2(0.35, -0.42); return vec2(0.0, 0.62);
  }
  if (k < 1.5) { // Cassiopeia
    if (i < 0.5) return vec2(-0.55, 0.1); if (i < 1.5) return vec2(-0.27, -0.15); if (i < 2.5) return vec2(0.0, 0.06);
    if (i < 3.5) return vec2(0.27, -0.2); if (i < 4.5) return vec2(0.55, 0.15); return vec2(9.0);
  }
  if (k < 2.5) { // the Plough
    if (i < 0.5) return vec2(-0.6, 0.25); if (i < 1.5) return vec2(-0.33, 0.3); if (i < 2.5) return vec2(-0.12, 0.2);
    if (i < 3.5) return vec2(0.08, 0.08); if (i < 4.5) return vec2(0.12, -0.2); if (i < 5.5) return vec2(0.52, -0.15);
    if (i < 6.5) return vec2(0.5, 0.12); return vec2(9.0);
  }
  if (k < 3.5) { // the Swan
    if (i < 0.5) return vec2(0.0, 0.52); if (i < 1.5) return vec2(0.0, 0.12); if (i < 2.5) return vec2(0.02, -0.5);
    if (i < 3.5) return vec2(-0.45, 0.18); if (i < 4.5) return vec2(0.45, 0.04); if (i < 5.5) return vec2(-0.22, 0.14);
    if (i < 6.5) return vec2(0.22, 0.08); return vec2(9.0);
  }
  if (k < 4.5) { // the Lion
    if (i < 0.5) return vec2(-0.35, -0.15); if (i < 1.5) return vec2(-0.4, 0.1); if (i < 2.5) return vec2(-0.3, 0.3);
    if (i < 3.5) return vec2(-0.12, 0.36); if (i < 4.5) return vec2(-0.05, 0.16); if (i < 5.5) return vec2(0.22, 0.12);
    if (i < 6.5) return vec2(0.52, -0.05); return vec2(0.22, -0.14);
  }
  // the Scorpion
  if (i < 0.5) return vec2(-0.5, 0.42); if (i < 1.5) return vec2(-0.36, 0.26); if (i < 2.5) return vec2(-0.14, 0.12);
  if (i < 3.5) return vec2(0.02, -0.06); if (i < 4.5) return vec2(0.12, -0.28); if (i < 5.5) return vec2(0.3, -0.4);
  if (i < 6.5) return vec2(0.48, -0.3); return vec2(0.45, -0.08);
}
// the lines: pairs of stars (« 9 »: none)
vec2 cline(float k, float j) {
  if (k < 0.5) {
    if (j < 0.5) return vec2(0, 2); if (j < 1.5) return vec2(1, 4); if (j < 2.5) return vec2(2, 3); if (j < 3.5) return vec2(3, 4);
    if (j < 4.5) return vec2(2, 5); if (j < 5.5) return vec2(4, 6); if (j < 6.5) return vec2(0, 7); return vec2(1, 7);
  }
  if (k < 1.5) { if (j < 3.5) return vec2(j, j + 1.0); return vec2(9.0); }
  if (k < 2.5) { if (j < 5.5) return vec2(j, j + 1.0); if (j < 6.5) return vec2(6, 3); return vec2(9.0); }
  if (k < 3.5) {
    if (j < 0.5) return vec2(0, 1); if (j < 1.5) return vec2(1, 2); if (j < 2.5) return vec2(3, 5); if (j < 3.5) return vec2(5, 1);
    if (j < 4.5) return vec2(1, 6); if (j < 5.5) return vec2(6, 4); return vec2(9.0);
  }
  if (k < 4.5) {
    if (j < 4.5) return vec2(j, j + 1.0); if (j < 5.5) return vec2(5, 6); if (j < 6.5) return vec2(6, 7); return vec2(7, 0);
  }
  if (j < 6.5) return vec2(j, j + 1.0); return vec2(9.0);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  float turn = t * 0.004;
  vec2 rp = mat2(cos(turn), -sin(turn), sin(turn), cos(turn)) * (p - vec2(0.5 * aspect, 0.5));
  o = over(o, vec3(1.0, 0.97, 0.9), starfield(rp, 80.0, t, 0.03));
  o = over(o, vec3(0.8, 0.85, 1.0), starfield(rp + 4.0, 150.0, t, 0.025) * 0.5);
  float period = 9.0;
  float k = mod(floor(t / period), 6.0);
  float cyc = mod(t, period);
  float fade = smoothstep(0.0, 0.6, cyc) * smoothstep(period, period - 1.4, cyc);
  vec2 centre = vec2((0.3 + 0.4 * hash(vec2(k, floor(t / 54.0)))) * aspect, 0.35 + 0.3 * hash(vec2(k + 3.0, floor(t / 54.0))));
  float scale = 0.55;
  vec2 q = (p - centre) / scale;
  float stars = 0.0;
  for (int i = 0; i < 8; i++) {
    float fi = float(i);
    vec2 s = cstar(k, fi);
    float born = 0.4 + fi * 0.35;
    float tw = 0.85 + 0.15 * sin(t * 3.0 + fi);
    stars += exp(-length(q - s) * 55.0) * smoothstep(born, born + 0.3, cyc) * tw;
    stars += exp(-length(q - s) * 14.0) * 0.12 * smoothstep(born, born + 0.3, cyc);
  }
  float lines = 0.0;
  for (int j = 0; j < 8; j++) {
    float fj = float(j);
    vec2 pair = cline(k, fj);
    if (pair.x > 8.5) continue;
    vec2 a = cstar(k, pair.x);
    vec2 b = cstar(k, pair.y);
    vec2 ab = b - a;
    float h = clamp(dot(q - a, ab) / dot(ab, ab), 0.0, 1.0);
    float drawn = clamp((cyc - 3.2 - fj * 0.35) / 0.4, 0.0, 1.0);
    lines += smoothstep(0.012, 0.0, length(q - a - ab * h)) * step(h, drawn);
  }
  float shine = 1.0 + 0.6 * exp(-abs(cyc - 6.5) * 2.0);
  o = over(o, vec3(0.5, 0.75, 1.0), clamp(lines, 0.0, 1.0) * 0.55 * fade * shine);
  o = over(o, vec3(1.0, 0.95, 0.85), clamp(stars, 0.0, 1.0) * fade);
  gl_FragColor = o;
}`;

/** The Milky Way: a band of countless stars across the sky, its glowing core, dark lanes of dust running
 * through it, drifting slowly over the mountains' silhouette. */
const MILKYWAY = `${SAFE_COMMON}${STARS}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  vec2 c = p - vec2(0.5 * aspect + t * 0.002, 0.45);
  float ang = 0.55;
  vec2 b = mat2(cos(ang), -sin(ang), sin(ang), cos(ang)) * c;
  float across = b.y + 0.06 * sin(b.x * 2.0);
  float band = exp(-across * across * 60.0);
  float core = exp(-dot((b - vec2(0.25, 0.0)) * vec2(1.0, 2.2), (b - vec2(0.25, 0.0)) * vec2(1.0, 2.2)) * 18.0);
  float clouds = fbm(b * vec2(2.5, 6.0) + vec2(t * 0.003, 0.0));
  float dust = smoothstep(0.5, 0.75, fbm(b * vec2(4.0, 14.0) + 3.0)) * exp(-across * across * 160.0);
  vec3 glow = mix(vec3(0.35, 0.4, 0.65), vec3(1.0, 0.85, 0.65), core);
  float a = (band * (0.16 + 0.34 * clouds) + core * 0.3) * (1.0 - dust * 0.85);
  o = over(o, glow, a);
  o = over(o, vec3(1.0, 0.97, 0.92), starfield(p, 110.0, t, 0.02 + band * 0.12) * (0.6 + 0.4 * band));
  o = over(o, vec3(0.85, 0.9, 1.0), starfield(p + 2.0, 220.0, t, 0.02 + band * 0.2) * band * 0.7);
  o = over(o, vec3(1.0, 0.95, 0.9), starfield(p + 7.0, 45.0, t, 0.012));
  float ridge = 0.11 + 0.06 * fbm(vec2(p.x * 2.5, 1.0)) + 0.04 * sin(p.x * 4.0 + 0.5);
  o = over(o, vec3(0.015, 0.02, 0.04), smoothstep(0.004, 0.0, uv.y - ridge) * 0.95);
  gl_FragColor = o;
}`;

/** A great comet passing: its glowing head crossing the sky over a minute, the curved golden dust tail
 * and the straight blue ion tail streaming away from the sun, stars behind. */
const COMETPASS = `${SAFE_COMMON}${STARS}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, vec3(1.0, 0.97, 0.9), starfield(p, 90.0, t, 0.03));
  float pass = fract(t / 70.0);
  vec2 head = vec2(mix(-0.1, aspect + 0.1, pass), 0.4 + 0.12 * sin(pass * 3.1416));
  vec2 away = normalize(vec2(-0.75, 0.55));
  vec2 rel = p - head;
  float along = dot(rel, away);
  float across = dot(rel, vec2(-away.y, away.x));
  // the dust tail: wide and curved, golden, fading with distance
  float bend = across - along * along * 0.25;
  float dust = smoothstep(0.03 + along * 0.22, 0.0, abs(bend)) * smoothstep(0.0, 0.04, along) * exp(-along * 0.9);
  dust *= 0.7 + 0.3 * fbm(vec2(along * 8.0 - t * 0.3, bend * 20.0));
  o = over(o, vec3(1.0, 0.86, 0.6), dust * 0.55);
  float ion = smoothstep(0.008 + along * 0.035, 0.0, abs(across + along * 0.04)) * smoothstep(0.0, 0.03, along) * exp(-along * 0.55);
  ion *= 0.6 + 0.4 * fbm(vec2(along * 20.0 - t * 1.2, across * 50.0));
  o = over(o, vec3(0.45, 0.7, 1.0), ion * 0.6);
  float hd = length(rel);
  o = over(o, vec3(0.6, 0.9, 0.95), exp(-hd * 18.0) * 0.6);
  o = over(o, vec3(1.0), exp(-hd * 160.0));
  gl_FragColor = o;
}`;

export const COSMOS_SHADERS: Record<string, string> = {
  orion: ORION,
  crab: CRAB,
  helix: HELIX,
  pillars: PILLARS,
  cliffs: CLIFFS,
  solarsystem: SOLARSYSTEM,
  saturnrise: SATURNRISE,
  perseids: PERSEIDS,
  constellations: CONSTELLATIONS,
  milkyway: MILKYWAY,
  greatcomet: COMETPASS,
};
