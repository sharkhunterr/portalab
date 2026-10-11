/**
 * #68: the premium ambiences drawn by the GPU — original fragment shaders built from the classic tools
 * (value noise, fractal Brownian motion, domain warping). Each writes premultiplied colour over a
 * transparent page: what is not lit stays see-through. Kept to GLSL ES 1.0 so every phone runs them.
 */

const COMMON = `
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif
uniform vec2 u_res;
uniform float u_time;
float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
             mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p = p * 2.03 + vec2(1.7, 9.2);
    a *= 0.5;
  }
  return v;
}
vec2 coords(out vec2 uv) {
  uv = gl_FragCoord.xy / u_res;
  return vec2(uv.x * u_res.x / u_res.y, uv.y);
}
`;

/** Flames rising from the bottom of the page, their heat shimmering, embers flying off. */
const INFERNO = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec2 q = vec2(p.x * 2.6, p.y * 1.8 - t * 1.1);
  float warp = fbm(q * 1.4 + vec2(0.0, -t * 0.7));
  float n = fbm(q + vec2(warp * 1.6, warp));
  float f = clamp((n * 1.5 + (0.3 - uv.y * 1.9) - 0.42) * 2.6, 0.0, 1.0);
  vec3 col = mix(vec3(0.45, 0.02, 0.0), vec3(1.0, 0.42, 0.04), smoothstep(0.05, 0.55, f));
  col = mix(col, vec3(1.0, 0.72, 0.28), smoothstep(0.6, 1.0, f));
  col *= 0.75 + 0.35 * fbm(q * 3.0 + t);  // the flame's inner flicker
  float a = smoothstep(0.02, 0.45, f) * 0.85;
  // embers: one in a few cells, rising and swaying
  vec2 g = vec2(p.x * 16.0, p.y * 9.0 - t * 2.2);
  vec2 id = floor(g);
  float r = hash(id);
  vec2 sway = vec2(sin(t * 1.7 + r * 6.28) * 0.28, (r - 0.5) * 0.5);
  float ember = step(0.88, r) * smoothstep(0.09, 0.0, length(fract(g) - 0.5 - sway));
  ember *= smoothstep(0.85, 0.1, uv.y) * (0.6 + 0.4 * sin(t * 6.0 + r * 40.0));
  col += vec3(1.0, 0.55, 0.15) * ember * 1.6;
  a = max(a, ember);
  gl_FragColor = vec4(col * a, a);
}`;

/** Heavy clouds rolling, rain in three depths, a lightning bolt lighting the clouds from inside. */
const THUNDERSTORM = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float k = floor(t / 6.0);
  float ph = mod(t, 6.0);
  float strikes = step(0.4, hash(vec2(k, 3.1)));
  float flash = strikes * (exp(-ph * 9.0) + 0.7 * exp(-abs(ph - 0.25) * 14.0));
  float c = fbm(vec2(p.x * 1.4 + t * 0.03, p.y * 2.4) + fbm(p * 2.0 + t * 0.05));
  float cloud = smoothstep(0.35, 0.85, c) * smoothstep(0.3, 0.95, uv.y);
  vec3 col = mix(vec3(0.22, 0.24, 0.3), vec3(0.58, 0.61, 0.7), c) + flash * vec3(0.55, 0.6, 0.8);
  float a = cloud * 0.8;
  float bx = (0.15 + 0.7 * hash(vec2(k, 7.0))) * u_res.x / u_res.y;
  float x = bx + (fbm(vec2(uv.y * 7.0, k)) - 0.5) * 0.3;
  float bolt = strikes * smoothstep(0.007, 0.0, abs(p.x - x)) * step(0.12, uv.y)
    * smoothstep(1.0, 0.65, uv.y) * exp(-ph * 5.0);
  col += vec3(0.85, 0.9, 1.0) * bolt * 3.0;
  a = max(a, bolt);
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float density = 36.0 + fi * 34.0;
    float length_ = 5.0 + fi * 3.0;
    vec2 r = vec2(p.x * density + p.y * density * 0.16, p.y * length_ + t * (4.0 + fi * 2.5));
    vec2 id = floor(r);
    vec2 f = fract(r);
    float drop = step(0.72, hash(id + fi * 13.0)) * smoothstep(0.07, 0.0, abs(f.x - 0.5))
      * smoothstep(0.0, 0.35, f.y) * smoothstep(1.0, 0.65, f.y);
    float w = 0.42 - fi * 0.1;
    col += vec3(0.7, 0.8, 0.95) * drop * w * 2.0;
    a = max(a, drop * w);
  }
  a = max(a, flash * 0.15);
  gl_FragColor = vec4(col * a, a);
}`;

/** Dust clouds swept by gusts, sand grains racing by, an orange veil over the page. */
const SANDSTORM = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float gust = 0.6 + 0.3 * sin(t * 0.35) + 0.15 * sin(t * 1.3 + 1.0);
  vec2 q = vec2(p.x * 1.8 - t * 0.45 * gust, p.y * 2.6);
  vec2 w = vec2(fbm(q + vec2(0.0, t * 0.08)), fbm(q + vec2(5.2, 1.3)));
  float d = fbm(q * 1.2 + w * 2.6);
  float dense = smoothstep(0.32, 0.9, d) * (0.5 + 0.4 * gust);
  vec3 col = mix(vec3(0.5, 0.29, 0.12), vec3(0.96, 0.74, 0.44), d);
  float a = dense * 0.72 + 0.1;
  vec2 g = vec2(p.x * 95.0 - t * 70.0 * gust, p.y * 95.0 + sin(p.x * 3.0 + t) * 3.0);
  float grain = step(0.985, hash(floor(g))) * smoothstep(0.5, 0.0, length(fract(g) - 0.5));
  col = mix(col, vec3(1.0, 0.86, 0.62), grain);
  a = max(a, grain * 0.8);
  gl_FragColor = vec4(col * a, a);
}`;

/** Polar lights: rippling curtains of green and violet over a starry sky. */
const POLAR = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec2 sg = p * 110.0;
  float sh = hash(floor(sg));
  float star = step(0.995, sh) * smoothstep(0.45, 0.0, length(fract(sg) - 0.5)) * (0.6 + 0.4 * sin(t * 2.5 + sh * 50.0));
  vec3 col = vec3(0.9, 0.95, 1.0) * star;
  float a = star * 0.8;
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float x = p.x * (1.1 + fi * 0.45) + t * 0.035 * (1.0 + fi);
    float base = 0.5 + 0.11 * fi + 0.1 * sin(x * 2.0 + t * 0.25 + fi) + 0.08 * fbm(vec2(x * 2.0, t * 0.08 + fi));
    float yd = uv.y - base;
    float band = smoothstep(-0.01, 0.03, yd) * exp(-max(yd, 0.0) * (3.5 + fi * 2.0));
    float rays = 0.55 + 0.45 * fbm(vec2(x * 14.0, t * 0.25 + fi * 3.0));
    float light = band * rays * (0.85 - fi * 0.2);
    vec3 tint = mix(vec3(0.12, 1.0, 0.55), vec3(0.6, 0.32, 1.0), clamp(yd * 2.6 + fi * 0.3, 0.0, 1.0));
    col += tint * light;
    a = max(a, light * 0.85);
  }
  gl_FragColor = vec4(col * a, a);
}`;

/** Deep space: a nebula slowly drifting, two depths of twinkling stars. */
const COSMOS = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec2 q = p * 1.1 + vec2(t * 0.012, t * 0.007);
  vec2 w = vec2(fbm(q * 1.3 + t * 0.02), fbm(q * 1.3 + vec2(3.3, 7.1) - t * 0.015));
  float n = fbm(q + w * 1.9);
  vec3 col = mix(vec3(0.15, 0.02, 0.3), vec3(0.1, 0.35, 0.8), w.x);
  col = mix(col, vec3(0.95, 0.35, 0.6), smoothstep(0.55, 0.85, n));
  float a = smoothstep(0.1, 0.62, n) * 0.6;
  for (int i = 0; i < 2; i++) {
    float fi = float(i);
    vec2 sg = (p + vec2(t * 0.004 * (fi + 1.0), 0.0)) * (70.0 + fi * 90.0);
    float sh = hash(floor(sg) + fi * 31.0);
    float star = step(0.994, sh) * smoothstep(0.45, 0.0, length(fract(sg) - 0.5))
      * (0.55 + 0.45 * sin(t * (1.5 + fi) + sh * 60.0));
    col += vec3(1.0, 0.96, 0.9) * star;
    a = max(a, star * (0.9 - fi * 0.3));
  }
  gl_FragColor = vec4(col * a, a);
}`;

/** Underwater: light caustics dancing, sun rays from the surface, bubbles rising. */
const ABYSS = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float n = fbm(p * 3.0 + fbm(p * 3.0 + t * 0.18) * 1.4 + t * 0.06);
  float n2 = fbm(p * 5.0 - fbm(p * 4.0 - t * 0.21) * 1.2 - t * 0.05);
  float caustic = pow(1.0 - abs(sin(n * 16.0)), 7.0) * pow(1.0 - abs(sin(n2 * 14.0)), 3.0) * 1.6;
  caustic *= smoothstep(0.05, 0.9, uv.y);
  float rays = (0.5 + 0.5 * sin(p.x * 9.0 + sin(p.x * 3.0 + t * 0.4) * 2.0 + t * 0.3))
    * (0.5 + 0.5 * sin(p.x * 23.0 - t * 0.5)) * smoothstep(0.25, 1.0, uv.y);
  vec3 col = vec3(0.35, 0.85, 1.0) * caustic + vec3(0.45, 0.8, 0.95) * rays * 0.35;
  float a = caustic * 0.5 + rays * 0.18;
  vec2 g = vec2(p.x * 9.0, p.y * 9.0 - t * 1.6);
  vec2 id = floor(g);
  float r = hash(id);
  vec2 wobble = vec2(sin(t * 2.0 + r * 9.0) * 0.2, 0.0);
  float ring = abs(length(fract(g) - 0.5 - wobble) - 0.07 - r * 0.06);
  float bubble = step(0.85, r) * smoothstep(0.025, 0.0, ring);
  col += vec3(0.8, 0.95, 1.0) * bubble;
  a = max(a, bubble * 0.7);
  col += vec3(0.0, 0.12, 0.22) * (1.0 - uv.y);
  a = max(a, (1.0 - uv.y) * 0.12);
  gl_FragColor = vec4(col * a, a);
}`;

/** A downpour: dense rain in four depths, splashes rippling at the bottom, mist rising off the ground. */
const DOWNPOUR = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec3 col = vec3(0.0);
  float a = 0.0;
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float density = 30.0 + fi * 30.0;
    float length_ = 4.0 + fi * 2.5;
    vec2 r = vec2(p.x * density + p.y * density * 0.08, p.y * length_ + t * (5.0 + fi * 2.2));
    vec2 id = floor(r);
    vec2 f = fract(r);
    float drop = step(0.6, hash(id + fi * 17.0)) * smoothstep(0.08, 0.0, abs(f.x - 0.5))
      * smoothstep(0.0, 0.4, f.y) * smoothstep(1.0, 0.7, f.y);
    float w = 0.32 - fi * 0.06;
    col += vec3(0.7, 0.78, 0.9) * drop * w * 2.0;
    a = max(a, drop * w);
  }
  vec2 s = vec2(p.x * 9.0, 0.0);
  float cell = floor(s.x);
  float born = hash(vec2(cell, floor(t * 1.5)));
  float age = fract(t * 1.5);
  float ring = abs(length(vec2(fract(s.x) - 0.5, (uv.y - 0.035) * 40.0)) - age * 0.4);
  float splash = step(0.55, born) * smoothstep(0.03, 0.0, ring) * (1.0 - age) * step(uv.y, 0.07);
  col += vec3(0.75, 0.82, 0.95) * splash;
  a = max(a, splash * 0.6);
  float mist = fbm(vec2(p.x * 2.0 + t * 0.1, p.y * 3.0)) * smoothstep(0.3, 0.0, uv.y);
  col += vec3(0.55, 0.6, 0.7) * mist * 0.5;
  a = max(a, mist * 0.35);
  gl_FragColor = vec4(col * a, a);
}`;

/** Digital rain: columns of glyphs drawn on a 5×7 grid, flickering, each column with its bright head
 * falling at its own pace and a fading trail; a faint glow behind. */
const MATRIX = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float columns = floor(u_res.x / u_res.y * 34.0);
  vec2 cellSize = vec2(1.0 / columns, 1.0 / 26.0);
  vec2 cell = floor(uv / cellSize);
  vec2 inCell = fract(uv / cellSize);
  float speed = 0.35 + hash(vec2(cell.x, 1.0)) * 0.9;
  float offset = hash(vec2(cell.x, 2.0)) * 40.0;
  float head = fract(t * speed * 0.08 + offset / 40.0);       // where the column's head is (0..1, falling)
  float row = 1.0 - (cell.y + 0.5) * cellSize.y;               // 0 at the top
  float behind = head - row;                                   // how far above the head this cell is
  float trail = behind >= 0.0 ? exp(-behind * 7.0) : 0.0;
  float second = fract(head + 0.5) - row;                      // a second, fainter drop per column
  trail = max(trail, second >= 0.0 ? exp(-second * 10.0) * 0.45 : 0.0);
  // the glyph: a random 5x7 dot pattern, changing now and then
  vec2 g = floor(vec2(inCell.x * 5.0, inCell.y * 7.0));
  float glyphSeed = floor(t * (1.5 + hash(cell) * 4.0));
  float bit = step(0.5, hash(cell * 7.13 + g * 1.31 + glyphSeed));
  vec2 dot_ = fract(vec2(inCell.x * 5.0, inCell.y * 7.0)) - 0.5;
  float lit = bit * smoothstep(0.5, 0.25, max(abs(dot_.x), abs(dot_.y)));
  lit *= step(0.12, inCell.x) * step(inCell.x, 0.88) * step(0.06, inCell.y) * step(inCell.y, 0.94);
  float isHead = smoothstep(cellSize.y * 1.2, 0.0, abs(behind));
  vec3 col = mix(vec3(0.05, 0.85, 0.35), vec3(0.85, 1.0, 0.9), isHead);
  float a = lit * trail * 0.9;
  float glow = trail * 0.06;
  gl_FragColor = vec4(col * a + vec3(0.0, 0.5, 0.2) * glow, max(a, glow));
}`;

export const SHADERS: Record<string, string> = {
  matrix: MATRIX,
  inferno: INFERNO,
  thunderstorm: THUNDERSTORM,
  sandstorm: SANDSTORM,
  polar: POLAR,
  cosmos: COSMOS,
  abyss: ABYSS,
  downpour: DOWNPOUR,
};
