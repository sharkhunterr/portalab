import { COMMON } from "./shaders";

/**
 * #68: the cosy ambiences — no scenery, no pixels: only warmth. Amber blobs drifting like a lava lamp,
 * candlelight breathing at the edges, curls of steam, soft out-of-focus fairy lights, folds of warm silk,
 * honey, a knitted blanket. Same rules as the others: premultiplied colour over a transparent page, light
 * enough to read through, GLSL ES 1.0.
 */

/** Amber glow: warm blobs rising and sinking slowly like a lava lamp, merging and parting, a soft rim of
 * light around them, a fine film grain. */
const AMBERGLOW = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, vec3(0.9, 0.45, 0.15), smoothstep(0.35, 0.95, length((uv - 0.5) * vec2(1.2, 1.0))) * 0.14);
  float field = 0.0;
  vec3 col = vec3(0.0);
  for (int i = 0; i < 7; i++) {
    float fi = float(i);
    float h1 = hash(vec2(fi, 1.0));
    float h2 = hash(vec2(fi, 2.0));
    vec2 c = vec2(aspect * (0.5 + 0.46 * sin(t * (0.03 + 0.03 * h1) + fi * 2.1)), 0.5 + 0.62 * sin(t * (0.05 + 0.04 * h2) + fi * 1.3));
    float r = 0.1 + 0.12 * hash(vec2(fi, 3.0));
    vec2 d = p - c;
    float f = r * r / max(dot(d, d), 1e-4);
    vec3 hue = i == 0 || i == 4 ? vec3(1.0, 0.55, 0.15) : i == 1 || i == 5 ? vec3(0.95, 0.35, 0.3) : i == 2 ? vec3(1.0, 0.75, 0.3) : vec3(0.85, 0.38, 0.15);
    field += f;
    col += hue * f;
  }
  col /= max(field, 1e-4);
  float glow = smoothstep(0.7, 1.4, field);
  float core = smoothstep(1.2, 4.0, field);
  o = over(o, mix(col, vec3(1.0, 0.86, 0.6), core * 0.4), glow * 0.22 + core * 0.1);
  o = over(o, vec3(1.0, 0.85, 0.6), (hash(gl_FragCoord.xy + floor(t * 12.0)) - 0.5) * 0.04 + 0.02);
  gl_FragColor = o;
}`;

/** Candlelight: halos of warm light breathing at the edges of the page, each flickering at its own pace and
 * swaying a little, soft shadows dancing between them, the corners in a warm dusk. (Golden dust floats in
 * the light as particles.) */
const CANDLELIGHT = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, vec3(0.25, 0.1, 0.04), smoothstep(0.3, 0.95, length((uv - 0.5) * vec2(1.1, 1.0))) * 0.45);
  float light = 0.0;
  for (int i = 0; i < 6; i++) {
    float fi = float(i);
    vec2 base = i == 0 ? vec2(0.06, 0.12) : i == 1 ? vec2(0.3, 0.0) : i == 2 ? vec2(0.68, 0.02) : i == 3 ? vec2(0.95, 0.18) : i == 4 ? vec2(0.03, 0.75) : vec2(0.97, 0.82);
    vec2 c = vec2(base.x * aspect, base.y) + vec2(noise(vec2(t * 1.3, fi)) - 0.5, noise(vec2(fi, t * 1.1)) - 0.5) * 0.02;
    float flick = 0.75 + 0.18 * noise(vec2(t * 5.0, fi * 7.0)) + 0.1 * noise(vec2(t * 13.0, fi * 3.0)) - 0.12 * step(0.97, hash(vec2(floor(t * 8.0), fi)));
    float d = length(p - c);
    light += (exp(-d * 4.5) * 0.6 + exp(-d * 16.0) * 0.5) * flick;
  }
  float shade = 0.75 + 0.25 * fbm(p * 1.6 + vec2(sin(t * 0.7), cos(t * 0.5)) * 0.15);
  light *= shade;
  o = over(o, vec3(1.0, 0.55, 0.18), clamp(light, 0.0, 1.0) * 0.55);
  o = over(o, vec3(1.0, 0.85, 0.55), smoothstep(0.7, 1.4, light) * 0.35);
  gl_FragColor = o;
}`;

/** Steam: curls of warm steam rising from the bottom of the page, twisting, thinning into nothing, lit
 * amber from below. */
const STEAM = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec4 o = vec4(0.0);
  o = over(o, vec3(1.0, 0.55, 0.2), smoothstep(0.45, 0.0, uv.y) * 0.16);
  float wisps = 0.0;
  for (int l = 0; l < 2; l++) {
    float fl = float(l);
    vec2 q = vec2(p.x * (2.0 + fl), p.y * 1.4 - t * (0.1 + fl * 0.05)) + fl * 7.0;
    vec2 w = vec2(fbm(q + vec2(0.0, t * 0.04)), fbm(q + vec2(5.2, -t * 0.03)));
    float f = fbm(q + w * 2.2);
    float curl = 1.0 - abs(2.0 * f - 1.0);
    wisps += pow(smoothstep(0.75, 1.0, curl), 2.5) * (0.8 - fl * 0.3);
  }
  float rise = smoothstep(0.7, 0.1, uv.y) * smoothstep(-0.05, 0.1, uv.y);
  vec3 col = mix(vec3(1.0, 0.72, 0.45), vec3(1.0, 0.95, 0.9), smoothstep(0.0, 0.7, uv.y));
  o = over(o, col, clamp(wisps * rise, 0.0, 1.0) * 0.4);
  gl_FragColor = o;
}`;

/** Fairy lights out of focus: warm points of light at three depths — small and sharp far away, large and
 * soft up close with a brighter rim like a lens draws them — drifting slowly and twinkling. */
const FAIRYBOKEH = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec4 o = vec4(0.0);
  o = over(o, vec3(0.5, 0.2, 0.08), 0.06);
  for (int l = 0; l < 3; l++) {
    float fl = float(l);
    float cell = 0.06 + fl * 0.07;
    vec2 g = (p + vec2(t * (0.004 + fl * 0.006), sin(t * 0.2 + fl) * 0.01)) / cell + fl * 3.7;
    vec2 id = floor(g);
    vec2 f = fract(g) - 0.5;
    float h = hash(id + fl * 11.0);
    if (h > (fl == 0.0 ? 0.78 : 0.5 + fl * 0.08)) {
      vec2 off = (vec2(hash(id + 1.0), hash(id + 2.0)) - 0.5) * 0.3;
      float r = 0.12 + 0.1 * fl + 0.08 * hash(id + 3.0);
      float d = length(f - off);
      float soft = 0.02 + fl * 0.06;
      float disc = smoothstep(r, r - soft, d);
      float rim = smoothstep(r - soft - 0.06, r - soft, d) * disc;
      float pick = hash(id + 4.0);
      vec3 col = pick < 0.4 ? vec3(1.0, 0.68, 0.3) : pick < 0.7 ? vec3(1.0, 0.82, 0.5) : pick < 0.88 ? vec3(1.0, 0.55, 0.35) : vec3(0.98, 0.45, 0.5);
      float tw = 0.6 + 0.4 * sin(t * (0.6 + hash(id + 5.0) * 1.5) + h * 30.0);
      float a = (fl == 0.0 ? 0.4 : fl == 1.0 ? 0.24 : 0.15) * tw;
      o = over(o, col, disc * a + rim * a * 0.6);
      o = over(o, col, exp(-d * 9.0) * a * 0.25);
    }
  }
  gl_FragColor = o;
}`;

/** Warm silk: wide folds of silk in copper, amber and rose rippling slowly, their sheen running along the
 * crests — strongest at the edges of the page, faint behind the content. */
const WARMSILK = `${COMMON}
float folds(vec2 p, float t) {
  return sin(p.x * 5.5 + sin(p.y * 3.2 + t * 0.21) * 1.8 + t * 0.12)
       + 0.5 * sin(p.x * 9.0 - p.y * 4.5 + t * 0.17 + sin(p.x * 2.1 + t * 0.09) * 2.0)
       + 0.25 * sin(p.y * 12.0 + p.x * 2.5 - t * 0.23);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec4 o = vec4(0.0);
  float h = folds(p, t);
  float e = 0.004;
  vec2 grad = vec2(folds(p + vec2(e, 0.0), t) - h, folds(p + vec2(0.0, e), t) - h) / e;
  vec3 n = normalize(vec3(-grad * 0.09, 1.0));
  vec3 light = normalize(vec3(-0.5, 0.6, 0.65));
  float diff = clamp(dot(n, light), 0.0, 1.0);
  float sheen = pow(clamp(dot(reflect(-light, n), vec3(0.0, 0.0, 1.0)), 0.0, 1.0), 18.0);
  vec3 base = mix(vec3(0.7, 0.28, 0.12), vec3(0.95, 0.5, 0.35), 0.5 + 0.25 * h);
  base = mix(base, vec3(1.0, 0.62, 0.2), smoothstep(0.3, 0.9, noise(p * 0.8 + t * 0.02)));
  vec3 col = base * (0.35 + 0.75 * diff) + vec3(1.0, 0.9, 0.75) * sheen * 0.8;
  float edge = smoothstep(0.2, 0.62, length((uv - 0.5) * vec2(1.3, 1.0)));
  o = over(o, col, 0.12 + 0.4 * edge);
  gl_FragColor = o;
}`;

/** Honey: a thick golden edge along the top of the page, drops gathering and stretching down from it and
 * letting go, a slow pool of honey at the bottom catching the light. */
const HONEY = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, vec3(1.0, 0.6, 0.15), 0.05);
  vec3 honey = vec3(0.95, 0.58, 0.1);
  vec3 deep = vec3(0.6, 0.28, 0.04);
  // the edge along the top, drops hanging from it
  float top = 0.95 - 0.015 * noise(vec2(p.x * 4.0, t * 0.1)) - 0.01 * sin(p.x * 3.0 + t * 0.2);
  float k = 9.0;
  float col_ = floor(p.x * k);
  float fx = fract(p.x * k) - 0.5;
  float h = hash(vec2(col_, 1.0));
  float period = 9.0 + 8.0 * h;
  float ph = fract(t / period + h);
  float len = 0.04 + 0.28 * smoothstep(0.0, 0.85, ph) * h;
  float hang = top - len;
  float strand = step(abs(fx), 0.05 + 0.12 * smoothstep(hang + 0.1, top, p.y)) * step(hang, p.y) * step(p.y, top + 0.01) * step(0.35, h);
  float bulb = smoothstep(1.0, 0.85, length(vec2(fx / 0.16, (p.y - hang) / 0.022))) * step(0.35, h) * step(ph, 0.85);
  // the drop letting go, falling
  float fall = (ph - 0.85) / 0.15;
  float dropY = hang - fall * fall * 1.1;
  float drop = smoothstep(1.0, 0.8, length(vec2(fx / 0.14, (p.y - dropY) / 0.024))) * step(0.85, ph) * step(0.35, h);
  float edge = step(top, p.y);
  float mass = clamp(edge + strand + bulb + drop, 0.0, 1.0);
  float shine = smoothstep(0.03, 0.0, abs(fx + 0.04)) * clamp(strand + bulb, 0.0, 1.0) + smoothstep(0.006, 0.0, abs(p.y - top - 0.012)) * edge;
  o = over(o, mix(deep, honey, 0.5 + 0.5 * (p.y - hang) / max(top - hang, 0.01)), mass * 0.85);
  o = over(o, vec3(1.0, 0.92, 0.7), shine * 0.6);
  // the pool at the bottom, slowly rippling, glinting
  float level = 0.08 + 0.008 * sin(p.x * 5.0 + t * 0.4) + 0.005 * sin(p.x * 11.0 - t * 0.3);
  float pool = step(p.y, level);
  float glint = 1.0 - abs(2.0 * fbm(vec2(p.x * 8.0 + t * 0.05, p.y * 30.0)) - 1.0);
  o = over(o, mix(deep, honey, smoothstep(0.0, level, p.y)), pool * 0.85);
  o = over(o, vec3(1.0, 0.9, 0.6), pool * smoothstep(0.95, 0.995, glint) * 0.3);
  o = over(o, vec3(1.0, 0.92, 0.7), smoothstep(0.004, 0.0, abs(p.y - level)) * 0.6);
  gl_FragColor = o;
}`;

/** A knitted blanket: rows of stitches in cream, rust and mustard with a little Nordic motif, their wool
 * fibres catching a warm light, the whole blanket breathing gently — thick around the edges, barely there
 * behind the content. */
const KNIT = `${COMMON}
float loop_(vec2 c, float side) {
  vec2 q = c - vec2(side * 0.22, 0.05);
  float a = side * 0.55;
  q = mat2(cos(a), -sin(a), sin(a), cos(a)) * q;
  return 1.0 - length(q / vec2(0.24, 0.5));
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec4 o = vec4(0.0);
  vec2 b = p + vec2(sin(p.y * 3.0 + t * 0.4), cos(p.x * 2.5 + t * 0.3)) * 0.006;
  vec2 g = b * vec2(34.0, 26.0);
  vec2 id = floor(g);
  vec2 c = fract(g) - 0.5;
  float l = loop_(c, -1.0);
  float r = loop_(c, 1.0);
  float stitch = max(l, r);
  float yarn = smoothstep(0.0, 0.15, stitch);
  float fibre = 0.8 + 0.2 * sin((c.x + c.y * (l > r ? 1.0 : -1.0)) * 60.0 + hash(id) * 6.0);
  // rows of colour and a small motif
  float row = mod(id.y, 14.0);
  vec3 cream = vec3(0.95, 0.88, 0.75);
  vec3 rust = vec3(0.72, 0.28, 0.14);
  vec3 mustard = vec3(0.88, 0.64, 0.22);
  vec3 col = row < 2.0 ? rust : row < 3.0 ? cream : row < 4.0 ? mustard : row < 10.0 ? cream : row < 11.0 ? mustard : row < 12.0 ? cream : rust;
  float mx = mod(id.x, 8.0);
  float my = row - 4.0;
  float motif = step(0.0, my) * step(my, 5.0) * step(abs(mx - 3.5) + abs(my - 2.5), 2.5) * step(1.5, abs(mx - 3.5) + abs(my - 2.5));
  col = mix(col, rust, motif);
  float lit = 0.75 + 0.35 * smoothstep(0.0, 0.45, stitch) - 0.2 * smoothstep(0.0, 0.3, c.y + 0.3);
  vec3 wool = col * lit * fibre;
  float edge = smoothstep(0.22, 0.6, length((uv - 0.5) * vec2(1.25, 1.0)));
  float breathe = 0.92 + 0.08 * sin(t * 0.5);
  o = over(o, vec3(0.2, 0.08, 0.04), (1.0 - yarn) * (0.05 + 0.33 * edge));
  o = over(o, wool * breathe, yarn * (0.06 + 0.6 * edge));
  o = over(o, vec3(1.0, 0.6, 0.25), smoothstep(1.0, 0.0, uv.y) * 0.04);
  gl_FragColor = o;
}`;

/** Lava lamp: big glossy blobs of wax in cheerful colours — pink, tangerine, lemon, turquoise, violet,
 * lime — warming at the bottom, rising slowly, stretching as they go, merging and splitting, cooling at the
 * top and sinking back; a pool of wax resting below, the light catching every curve. */
const LAVALAMP = `${COMMON}
vec3 waxColour(int i) {
  return i == 0 ? vec3(1.0, 0.25, 0.6) : i == 1 ? vec3(1.0, 0.55, 0.12) : i == 2 ? vec3(1.0, 0.85, 0.2)
       : i == 3 ? vec3(0.15, 0.82, 0.82) : i == 4 ? vec3(0.6, 0.35, 1.0) : i == 5 ? vec3(0.55, 0.9, 0.3)
       : i == 6 ? vec3(1.0, 0.4, 0.4) : i == 7 ? vec3(0.3, 0.6, 1.0) : vec3(1.0, 0.65, 0.85);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, mix(vec3(1.0, 0.45, 0.6), vec3(0.45, 0.35, 1.0), uv.y), 0.07);
  float field = 0.0;
  vec2 grad = vec2(0.0);
  vec3 col = vec3(0.0);
  for (int i = 0; i < 9; i++) {
    float fi = float(i);
    float h1 = hash(vec2(fi, 1.0));
    float h2 = hash(vec2(fi, 2.0));
    float speed = 0.05 + 0.05 * h2;
    float ph = t * speed + fi * 1.9;
    // lingering at the bottom and the top, moving in between
    float cyc = sin(ph);
    float y = 0.5 - 0.62 * cyc * (1.2 - 0.2 * cyc * cyc);
    float vy = abs(cos(ph));
    float x = aspect * (0.08 + 0.84 * h1) + 0.06 * sin(t * 0.07 + fi * 2.7);
    float r = 0.085 + 0.09 * hash(vec2(fi, 3.0));
    float stretch = 1.0 + 0.45 * vy;
    vec2 d = (p - vec2(x, y)) * vec2(1.0, 1.0 / stretch);
    float f = 1.7 * exp(-dot(d, d) / (r * r));
    field += f;
    grad += -2.0 * f / (r * r) * d;
    col += waxColour(i) * f * f;
  }
  // the pool of wax at the bottom and a little at the top
  float pool = 1.4 * exp(-max(p.y, 0.0) * 13.0) * (0.85 + 0.15 * sin(p.x * 6.0 + t * 0.2));
  float cap = 0.5 * exp(-max(1.0 - p.y, 0.0) * 16.0);
  field += pool + cap;
  grad += vec2(0.0, -13.0 * pool + 16.0 * cap);
  col += vec3(1.0, 0.35, 0.55) * pool * pool + vec3(0.5, 0.4, 1.0) * cap * cap;
  col /= max(max(max(col.r, col.g), col.b), 1e-4); // the colour of whichever blob is nearest, blended where they meet
  float body = smoothstep(0.95, 1.1, field);
  float glow = smoothstep(0.7, 1.0, field) * (1.0 - body);
  vec3 n = normalize(vec3(-grad * 0.035, 1.0));
  vec3 l = normalize(vec3(-0.4, 0.5, 0.8));
  float diff = clamp(dot(n, l), 0.0, 1.0);
  float spec = pow(clamp(dot(reflect(-l, n), vec3(0.0, 0.0, 1.0)), 0.0, 1.0), 24.0);
  float rimDark = smoothstep(1.6, 1.0, field);
  vec3 wax = col * (0.55 + 0.6 * diff) * (1.0 - 0.25 * rimDark) + vec3(1.0) * spec * 0.7;
  float edge = smoothstep(0.2, 0.6, length((uv - 0.5) * vec2(1.25, 1.0)));
  o = over(o, col, glow * 0.07);
  o = over(o, wax, body * (0.6 + 0.3 * edge));
  gl_FragColor = o;
}`;

/** Thick paint: the shared tools of the impasto ambiences — glossy acrylic in pop colours (pink, lemon,
 * sky blue, tangerine, violet, a streak of white), each colour a ridge of its own with the brush's fine
 * grooves running along it, lit like wet paint. */
const THICKPAINT = `${COMMON}
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
vec3 popInk(float u) {
  float x = fract(u) * 6.0;
  float i = floor(x);
  float f = fract(x);
  vec3 a = i < 1.0 ? vec3(1.0, 0.2, 0.6) : i < 2.0 ? vec3(1.0, 0.86, 0.12) : i < 3.0 ? vec3(0.2, 0.72, 1.0)
         : i < 4.0 ? vec3(1.0, 0.55, 0.1) : i < 5.0 ? vec3(0.45, 0.25, 0.88) : vec3(0.97, 0.96, 1.0);
  vec3 b = i < 1.0 ? vec3(1.0, 0.86, 0.12) : i < 2.0 ? vec3(0.2, 0.72, 1.0) : i < 3.0 ? vec3(1.0, 0.55, 0.1)
         : i < 4.0 ? vec3(0.45, 0.25, 0.88) : i < 5.0 ? vec3(0.97, 0.96, 1.0) : vec3(1.0, 0.2, 0.6);
  return mix(a, b, smoothstep(0.86, 1.0, f));
}
// lights paint of this colour whose surface slopes by grad
vec3 litPaint(vec2 grad, vec3 ink) {
  vec3 n = normalize(vec3(-grad, 1.0));
  vec3 l = normalize(vec3(-0.45, 0.6, 0.65));
  float diff = clamp(dot(n, l), 0.0, 1.0);
  float spec = pow(clamp(dot(reflect(-l, n), vec3(0.0, 0.0, 1.0)), 0.0, 1.0), 36.0);
  return ink * (0.45 + 0.7 * diff) + vec3(1.0) * spec * 0.85;
}
`;

/** Impasto: the whole page in thick glossy paint swirling slowly around a wandering centre — pop colours
 * folding into one another, every stroke raised, grooved by the brush and shining. Lighter behind the
 * content, full colour at the edges. */
const IMPASTO = `${THICKPAINT}
float bands(vec2 p, float t, float aspect) {
  vec2 c = vec2(aspect * (0.55 + 0.08 * sin(t * 0.05)), 0.5 + 0.1 * cos(t * 0.04));
  vec2 d = p - c;
  float r = length(d);
  float a = atan(d.y, d.x) + 1.1 / (r + 0.35) + t * 0.035;
  vec2 q = vec2(cos(a), sin(a)) * r;
  q += 0.22 * vec2(fbm4(q * 2.0 + t * 0.02), fbm4(q * 2.0 + 5.3 - t * 0.02));
  return r * 1.1 + fbm4(q * 1.6) * 1.7 + q.x * 0.3;
}
float relief(float u) {
  // smooth from one colour to the next: no crease where two colours meet (it lit as a crack)
  return (0.5 - 0.5 * cos(u * 6.0 * 6.2831)) * 0.6 + 0.008 * sin(u * 260.0);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  float e = 2.5 / u_res.y;
  float u = bands(p, t, aspect);
  float ux = bands(p + vec2(e, 0.0), t, aspect);
  float uy = bands(p + vec2(0.0, e), t, aspect);
  float h = relief(u);
  vec2 grad = vec2(relief(ux) - h, relief(uy) - h) / e * 0.018;
  vec3 col = litPaint(grad, popInk(u));
  float edge = smoothstep(0.18, 0.62, length((uv - 0.5) * vec2(1.25, 1.0)));
  gl_FragColor = over(vec4(0.0), col, 0.3 + 0.55 * edge);
}`;

/** Ribbons of paint: thick strokes of glossy pop paint waving across the page — one low, a thinner one
 * high — their colours running side by side, their edges torn, everything else left clear. */
const PAINTRIBBON = `${THICKPAINT}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec4 o = vec4(0.0);
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float base = fk == 0.0 ? 0.22 : 0.84;
    float amp = fk == 0.0 ? 0.11 : 0.05;
    float e = 2.5 / u_res.y;
    // the stroke's centre line and width, at the point and a little right and up (for the light)
    vec3 h3 = vec3(0.0);
    float u = 0.0;
    float inside = 0.0;
    for (int j = 0; j < 3; j++) {
      vec2 q = p + (j == 1 ? vec2(e, 0.0) : j == 2 ? vec2(0.0, e) : vec2(0.0));
      float mid = base + amp * sin(q.x * 2.1 + t * 0.28 + fk * 2.0) + amp * 0.45 * sin(q.x * 4.7 - t * 0.21 + fk);
      float w = (fk == 0.0 ? 0.15 : 0.05) * (0.75 + 0.35 * sin(q.x * 2.9 + t * 0.23 + fk * 3.0));
      float across = (q.y - mid) / w;
      float torn = 0.12 * (fbm4(vec2(q.x * 9.0, fk * 5.0 + t * 0.03)) - 0.5) * 2.0;
      float uu = across * 0.42 + fbm4(vec2(q.x * 2.5 - t * 0.05, across * 0.8 + fk * 7.0)) * 0.6 + fk * 0.37;
      float dome = sqrt(max(1.0 - across * across, 0.0));
      float hh = (dome * 0.8 + (0.5 - 0.5 * cos(uu * 6.0 * 6.2831)) * 0.35 + 0.01 * sin(uu * 260.0)) * 0.02;
      if (j == 0) {
        u = uu;
        inside = smoothstep(1.0 + torn, 0.92 + torn, abs(across));
        h3.x = hh;
      } else if (j == 1) {
        h3.y = hh;
      } else {
        h3.z = hh;
      }
    }
    vec3 col = litPaint(vec2(h3.y - h3.x, h3.z - h3.x) / e, popInk(u));
    o = over(o, col, inside * 0.95);
  }
  gl_FragColor = o;
}`;

/** The paints: five inks with soft but visible borders between them, like paints that have not quite
 * blended — warm (burgundy, terracotta, coral, ochre, cream) or pop. */
const WARM_INKS = `
  vec3 c0 = vec3(0.55, 0.12, 0.16);
  vec3 c1 = vec3(0.86, 0.36, 0.2);
  vec3 c2 = vec3(0.98, 0.52, 0.42);
  vec3 c3 = vec3(0.96, 0.7, 0.28);
  vec3 c4 = vec3(0.98, 0.9, 0.76);`;
/** Pop: hot pink, tangerine, lemon, turquoise and violet, straight from the tube. */
const POP_INKS = `
  vec3 c0 = vec3(0.55, 0.2, 0.95);
  vec3 c1 = vec3(1.0, 0.18, 0.55);
  vec3 c2 = vec3(1.0, 0.55, 0.1);
  vec3 c3 = vec3(1.0, 0.86, 0.15);
  vec3 c4 = vec3(0.1, 0.82, 0.8);`;
function paint(inks: string): string {
  return `${COMMON}
vec3 paintColour(float x) {
  x = fract(x);${inks}
  float b = 0.035;
  vec3 c = mix(c0, c1, smoothstep(0.2 - b, 0.2 + b, x));
  c = mix(c, c2, smoothstep(0.4 - b, 0.4 + b, x));
  c = mix(c, c3, smoothstep(0.6 - b, 0.6 + b, x));
  c = mix(c, c4, smoothstep(0.8 - b, 0.8 + b, x));
  return mix(c, c0, smoothstep(0.96, 1.0, x));
}
float edgeOf(vec2 uv) {
  return smoothstep(0.18, 0.62, length((uv - 0.5) * vec2(1.25, 1.0)));
}
`;
}

/** Paint stirred: warm paints swirled together by a slow stirring, folding into one another without quite
 * blending, the brush's fine streaks following the flow. */
const PAINTMIX = `
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec2 q = p * 1.1;
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    q += 0.3 * vec2(sin(q.y * 1.7 + t * 0.06 + fi * 1.7), cos(q.x * 1.4 - t * 0.05 + fi * 2.3));
  }
  float v = noise(q * 0.8 + vec2(t * 0.012, -t * 0.008)) * 0.65 + noise(q * 1.7 - t * 0.01) * 0.35;
  vec3 col = paintColour(v * 1.6 + 0.04 * sin(t * 0.03));
  float streak = 0.95 + 0.05 * sin(v * 70.0 + q.x * 2.0);
  float sheen = smoothstep(0.6, 1.0, noise(q * 3.0 + t * 0.02)) * 0.12;
  gl_FragColor = over(vec4(0.0), col * streak + sheen, 0.26 + 0.4 * edgeOf(uv));
}`;

/** Acrylic pour: warm paints poured and flowing slowly, cells of white opening and closing where the
 * colours meet, threads of gold running through. */
const ACRYLICPOUR = `
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec2 q = p * 1.1 + vec2(t * 0.01, 0.0);
  vec2 w = vec2(fbm(q + vec2(0.0, t * 0.02)), fbm(q + vec2(4.1, -t * 0.015)));
  vec2 r = q + w * 1.8;
  float v = fbm(r);
  vec3 col = paintColour(v * 1.5 + 0.2);
  // cells where the paints meet: rings of the lighter paint breaking through
  float zone = smoothstep(0.08, 0.0, abs(v - 0.52)) + smoothstep(0.06, 0.0, abs(v - 0.38)) * 0.7;
  float cellNoise = noise(r * 14.0 + w * 3.0);
  float cells = smoothstep(0.08, 0.0, abs(cellNoise - 0.55)) * zone;
  float holes = smoothstep(0.6, 0.7, cellNoise) * zone;
  col = mix(col, vec3(0.98, 0.93, 0.85), clamp(cells * 0.9 + holes * 0.5, 0.0, 1.0));
  float vein = 1.0 - abs(2.0 * fbm(r * 2.0 + 7.0) - 1.0);
  col = mix(col, vec3(1.0, 0.8, 0.35), smoothstep(0.96, 0.995, vein) * 0.8);
  gl_FragColor = over(vec4(0.0), col, 0.24 + 0.42 * edgeOf(uv));
}`;

/** Watercolour: blooms of warm pigment spreading on wet paper, darker at their rims where the colour
 * gathers, grainy, overlapping, fading as new ones open. */
const WATERCOLOR = `
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  float paper = 0.9 + 0.1 * noise(p * 300.0);
  o = over(o, vec3(0.98, 0.9, 0.78), 0.035 * paper);
  for (int i = 0; i < 9; i++) {
    float fi = float(i);
    float life = 14.0 + 8.0 * hash(vec2(fi, 1.0));
    float tt = t + hash(vec2(fi, 2.0)) * life;
    float slot = floor(tt / life);
    float ph = fract(tt / life);
    vec2 c = vec2(aspect * hash(vec2(slot, fi + 3.0)), hash(vec2(slot, fi + 4.0)));
    float r = (0.2 + 0.25 * hash(vec2(slot, fi + 5.0))) * (1.0 - pow(1.0 - min(ph * 1.6, 1.0), 3.0));
    vec2 d = p - c;
    float a = atan(d.y, d.x);
    vec2 dir = vec2(cos(a), sin(a));
    float wobble = 0.6 + 0.5 * noise(dir * 1.6 + vec2(fi * 3.0 + slot, 0.0)) + 0.12 * noise(dir * 5.0 + d * 4.0 + fi);
    float dist = length(d) / max(r * wobble, 1e-3);
    float inside = smoothstep(1.0, 0.85, dist);
    float rim = smoothstep(0.82, 0.98, dist) * inside;
    float grain = 0.88 + 0.12 * noise(p * 90.0 + fi);
    float bleed = 0.6 + 0.4 * fbm(d * 6.0 + fi);
    float fade = smoothstep(1.0, 0.7, ph);
    vec3 col = paintColour(hash(vec2(slot, fi + 6.0)) * 0.95);
    o = over(o, col * grain, (inside * 0.26 * bleed + rim * 0.24) * fade * (0.7 + 0.6 * edgeOf(uv)));
  }
  gl_FragColor = o;
}`;

/** Marbled paper: warm inks floated on water and combed into fine stripes, drifting and folding slowly
 * like the endpapers of an old book. */
const MARBLING = `
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec2 q = p;
  q.y += 0.08 * sin(q.x * 4.0 + t * 0.1);
  q.x += 0.06 * sin(q.y * 9.0 - t * 0.07);
  q.y += 0.04 * sin(q.x * 13.0 + t * 0.05);
  q += 0.25 * vec2(fbm(q * 1.5 + t * 0.02), fbm(q * 1.5 + 3.0 - t * 0.02));
  float stripes = q.y * 5.0 + fbm(q * 3.0) * 1.2;
  vec3 col = paintColour(stripes * 0.5);
  float line = smoothstep(0.08, 0.0, abs(fract(stripes * 2.0) - 0.5) - 0.42);
  col = mix(col, vec3(0.35, 0.08, 0.1), line * 0.5);
  gl_FragColor = over(vec4(0.0), col, 0.24 + 0.42 * edgeOf(uv));
}`;

export const WARM_SHADERS: Record<string, string> = {
  amberglow: AMBERGLOW,
  candlelight: CANDLELIGHT,
  steam: STEAM,
  fairybokeh: FAIRYBOKEH,
  warmsilk: WARMSILK,
  honey: HONEY,
  knit: KNIT,
  paintmix: paint(WARM_INKS) + PAINTMIX,
  acrylicpour: paint(WARM_INKS) + ACRYLICPOUR,
  watercolor: paint(WARM_INKS) + WATERCOLOR,
  marbling: paint(WARM_INKS) + MARBLING,
  lavalamp: LAVALAMP,
  impasto: IMPASTO,
  paintribbon: PAINTRIBBON,
  poppaint: paint(POP_INKS) + PAINTMIX,
  poppour: paint(POP_INKS) + ACRYLICPOUR,
  popwatercolor: paint(POP_INKS) + WATERCOLOR,
  popmarbling: paint(POP_INKS) + MARBLING,
};
