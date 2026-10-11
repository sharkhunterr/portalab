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
  mat2 turn = mat2(0.8, 0.6, -0.6, 0.8); // each octave turned: no grid lines
  for (int i = 0; i < 6; i++) {
    v += a * noise(p);
    p = turn * p * 2.03 + vec2(1.7, 9.2);
    a *= 0.5;
  }
  return v;
}
// lays a layer of colour c with coverage al over what is already drawn (premultiplied)
vec4 over(vec4 under, vec3 c, float al) {
  al = clamp(al, 0.0, 1.0);
  return vec4(c * al + under.rgb * (1.0 - al), al + under.a * (1.0 - al));
}
float fwidthApprox(float z) {
  return clamp(z * 0.004, 0.0, 0.2);
}
vec2 coords(out vec2 uv) {
  uv = gl_FragCoord.xy / u_res;
  return vec2(uv.x * u_res.x / u_res.y, uv.y);
}
`;

/** Flames rising from the bottom of the page: tongues of fire torn by turbulence, a hot core and a
 * flickering crest (the embers are particles of their own, carried by the heat). */
const INFERNO = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec2 q = vec2(p.x * 2.4, p.y * 1.6 - t * 1.25);
  vec2 warp = vec2(fbm(q * 1.3 + vec2(0.0, -t * 0.6)), fbm(q * 1.7 + vec2(5.2, -t * 0.9)));
  float n = fbm(q + warp * 1.8);
  float tongues = 1.0 - abs(noise(vec2(p.x * 9.0 + warp.x * 3.0, p.y * 3.0 - t * 2.4)) * 2.0 - 1.0);
  n += tongues * 0.18;
  float f = clamp((n * 1.5 + (0.3 - uv.y * 1.9) - 0.42) * 2.6, 0.0, 1.0);
  vec3 col = mix(vec3(0.42, 0.02, 0.0), vec3(1.0, 0.4, 0.03), smoothstep(0.05, 0.5, f));
  col = mix(col, vec3(1.0, 0.72, 0.28), smoothstep(0.55, 1.0, f));
  col *= 0.78 + 0.32 * fbm(q * 3.5 + t * 1.3);
  float a = smoothstep(0.02, 0.4, f) * 0.85;
  // a dim glow above the flames
  float glow = smoothstep(0.55, 0.0, uv.y) * 0.18 * (0.8 + 0.2 * sin(t * 3.0));
  col += vec3(0.6, 0.15, 0.0) * glow;
  a = max(a, glow);
  gl_FragColor = vec4(col * a, a);
}`;

/** A thunderstorm: heavy clouds rolling in layers, lit from inside; lightning at random moments — a
 * forked bolt with its glow and a double flicker, the clouds around it flaring — and distant sheet
 * lightning glowing in the clouds. (The rain is particles of its own, slanting with the gusts.) */
const THUNDERSTORM = `${COMMON}
float bolt(vec2 p, float x0, float top, float seed, float width) {
  // a jagged path down from the clouds: coarse turns and fine jitter
  float y = p.y;
  float x = x0 + (fbm(vec2(y * 2.2, seed)) - 0.5) * 0.55 + (noise(vec2(y * 18.0, seed * 3.0)) - 0.5) * 0.05;
  float d = abs(p.x - x);
  float along = step(top, y) * smoothstep(top, top + 0.04, y) * step(y, 1.05);
  return along * (smoothstep(width, 0.0, d) + exp(-d * 55.0) * 0.35);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  // strikes at random moments: one chance per slot of 2.3 s
  float slot = floor(t / 2.3);
  float ph = mod(t, 2.3);
  float strikes = step(0.55, hash(vec2(slot, 3.1)));
  float flicker = exp(-ph * 10.0) + 0.8 * exp(-abs(ph - 0.16) * 22.0) + 0.4 * exp(-abs(ph - 0.31) * 30.0);
  float flash = strikes * flicker;
  float bx = (0.12 + 0.76 * hash(vec2(slot, 7.0))) * aspect;
  vec2 strikeAt = vec2(bx, 0.78);
  // clouds: two layers drifting at their own pace, a domain warp folding them
  vec2 q = vec2(p.x * 1.3 + t * 0.025, p.y * 2.2);
  vec2 w = vec2(fbm(q * 1.1 + t * 0.03), fbm(q * 1.1 + vec2(5.0, -t * 0.02)));
  float c1 = fbm(q + w * 1.4);
  float c2 = fbm(q * 2.3 + w * 2.0 + vec2(t * 0.05, 0.0));
  float cloud = smoothstep(0.26, 0.72, c1 * 0.7 + c2 * 0.3) * smoothstep(0.25, 0.85, uv.y);
  // dark heavy bellies, lighter rims where the cloud thins
  vec3 col = mix(vec3(0.2, 0.21, 0.27), vec3(0.55, 0.58, 0.68), smoothstep(0.35, 0.85, c2));
  col *= 0.8 + 0.35 * smoothstep(0.4, 0.9, uv.y);
  // lightning lights the clouds from inside, strongest around the strike
  float near = exp(-length((p - strikeAt) * vec2(1.0, 1.6)) * 2.2);
  col += vec3(0.6, 0.65, 0.9) * cloud * flash * (0.35 + 1.4 * near);
  // distant sheet lightning: a glow wandering in the clouds
  float far = step(0.8, hash(vec2(floor(t / 1.1), 11.0))) * exp(-mod(t, 1.1) * 6.0);
  vec2 farAt = vec2(hash(vec2(floor(t / 1.1), 2.0)) * aspect, 0.85);
  col += vec3(0.45, 0.5, 0.75) * cloud * far * exp(-length(p - farAt) * 3.0) * 0.9;
  float a = cloud * 0.9;
  // the bolt and two branches, fading after the first flicker
  float life = strikes * exp(-ph * 3.2);
  float b = bolt(p, bx, 0.18, slot, 0.0035);
  float br1 = bolt(vec2(p.x - (0.62 - p.y) * 0.25, p.y), bx + 0.02, 0.42, slot + 4.0, 0.0022)
    * step(p.y, 0.62);
  float br2 = bolt(vec2(p.x + (0.5 - p.y) * 0.35, p.y), bx - 0.03, 0.3, slot + 9.0, 0.0018)
    * step(p.y, 0.5) * step(0.5, hash(vec2(slot, 13.0)));
  float light = (b + br1 * 0.7 + br2 * 0.55) * life * flicker;
  col += vec3(0.86, 0.9, 1.0) * light * 2.5;
  a = max(a, clamp(light, 0.0, 1.0));
  // the whole sky brightens for an instant
  a = max(a, flash * 0.12);
  col += vec3(0.5, 0.55, 0.7) * flash * 0.12;
  gl_FragColor = vec4(col * a, a);
}`;

/** Dust swept by gusts: billows that roll, reshape and thicken (a double domain warp evolving with
 * time), fine wind streaks racing through, an orange veil breathing with the gusts. The grains are
 * particles of their own, carried by a turbulent flow. */
const SANDSTORM = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float gust = 0.55 + 0.3 * sin(t * 0.31) + 0.2 * sin(t * 0.97 + 1.3) + 0.1 * sin(t * 2.3);
  vec2 q = p * vec2(1.6, 2.2);
  vec2 w1 = vec2(fbm(q * 0.9 + vec2(-t * 0.22 * gust, t * 0.05)), fbm(q * 0.9 + vec2(4.1 - t * 0.18, 1.7 + t * 0.07)));
  vec2 w2 = vec2(fbm(q * 1.7 + w1 * 2.0 + vec2(-t * 0.35, 0.0)), fbm(q * 1.7 + w1 * 2.0 + vec2(8.3, -t * 0.1)));
  float d = fbm(q * 1.1 + w2 * 2.4 + vec2(-t * 0.5 * gust, 0.0));
  float dense = smoothstep(0.28, 0.95, d) * (0.45 + 0.45 * gust);
  float streak = fbm(vec2(q.x * 0.6 - t * 1.3 * gust, q.y * 16.0 + w1.x * 3.0));
  dense += smoothstep(0.62, 0.85, streak) * 0.1;
  vec3 col = mix(vec3(0.45, 0.26, 0.11), vec3(0.97, 0.78, 0.5), clamp(d + 0.2 * w2.y, 0.0, 1.0));
  float a = clamp(dense, 0.0, 1.0) * 0.68 + 0.06 + 0.06 * gust;
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
    float h2 = hash(id * 1.3 + fi * 7.0);
    float drop = step(0.58, hash(id + fi * 17.0)) * smoothstep(0.035, 0.0, abs(f.x - 0.2 - 0.6 * h2))
      * smoothstep(0.0, 0.35, f.y) * smoothstep(1.0, 0.5 + 0.35 * h2, f.y);
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

/** A volcano: a field of lava at the bottom — glowing veins cracking a dark crust, flowing slowly and
 * pulsing — a plume of ash rising above it, lit red from below. (Ash and sparks are particles.) */
const VOLCANO = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  // lava: ridged veins through a crust, flowing to the side and pulsing
  vec2 q = vec2(p.x * 3.0 + t * 0.04, uv.y * 7.0 - t * 0.05);
  vec2 w = vec2(fbm(q * 0.7 + t * 0.03), fbm(q * 0.7 + vec2(3.7, -t * 0.02)));
  float n = fbm(q + w * 1.6);
  float vein = smoothstep(0.07, 0.0, abs(n - 0.5)) + 0.5 * smoothstep(0.16, 0.0, abs(n - 0.5));
  float pulse = 0.75 + 0.25 * sin(t * 1.3 + n * 9.0);
  float field = smoothstep(0.36, 0.08, uv.y);
  vec3 lava = mix(vec3(0.9, 0.18, 0.02), vec3(1.0, 0.75, 0.25), clamp(vein - 0.4, 0.0, 1.0)) * pulse;
  vec3 crust = vec3(0.08, 0.03, 0.02) + vec3(0.25, 0.05, 0.0) * fbm(q * 3.0);
  vec3 col = mix(crust, lava, clamp(vein, 0.0, 1.0)) * field;
  float a = field * (0.55 + 0.45 * clamp(vein, 0.0, 1.0));
  // the plume: ash billowing up, lit red where it is low
  vec2 r = vec2(p.x * 1.6, uv.y * 2.0 - t * 0.12);
  vec2 wr = vec2(fbm(r + t * 0.05), fbm(r + vec2(6.1, 2.3)));
  float ash = fbm(r * 1.3 + wr * 2.2);
  float plume = smoothstep(0.42, 0.85, ash) * smoothstep(0.15, 0.55, uv.y) * smoothstep(1.1, 0.5, uv.y);
  vec3 smoke = mix(vec3(0.12, 0.1, 0.1), vec3(0.35, 0.3, 0.3), ash);
  smoke += vec3(0.6, 0.12, 0.02) * smoothstep(0.65, 0.2, uv.y) * (0.6 + 0.4 * sin(t * 1.3));
  col = mix(col, smoke, plume * (1.0 - field));
  a = max(a, plume * 0.85);
  float glow = smoothstep(0.6, 0.1, uv.y) * 0.25 * pulse;
  col += vec3(0.7, 0.12, 0.0) * glow;
  a = max(a, glow);
  gl_FragColor = vec4(col * a, a);
}`;

/** A black hole: a swirling accretion disc, brighter on the side turning toward us, its far side lensed
 * over the hole into a ring of light; the stars behind bent around it; the horizon pure black. */
const BLACKHOLE = `${COMMON}
float stars(vec2 p) {
  vec2 g = p * 90.0;
  float h = hash(floor(g));
  return step(0.992, h) * smoothstep(0.5, 0.0, length(fract(g) - 0.5)) * (0.5 + 0.5 * h);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec2 c = vec2(aspect * 0.68, 0.56);
  vec2 q = p - c;
  float r = length(q);
  float R = 0.085;
  // the stars behind, bent around the hole
  float bend = R * R * 1.8 / max(r, 0.001);
  vec2 lensed = c + normalize(q) * max(r - bend, 0.0) + vec2(t * 0.003, 0.0);
  vec3 col = vec3(0.9, 0.93, 1.0) * stars(lensed) * smoothstep(R, R * 2.5, r);
  float a = stars(lensed) * 0.85 * smoothstep(R, R * 2.5, r);
  // the disc, tilted: bright, turbulent, spinning faster near the hole
  vec2 d = vec2(q.x, q.y * 3.4);
  float rd = length(d);
  float ang = atan(d.y, d.x);
  float spin = t * (0.9 / max(rd, 0.05));
  float swirl = fbm(vec2(ang * 2.0 + spin, rd * 14.0 - t * 0.3));
  float band = smoothstep(R * 1.4, R * 1.9, rd) * smoothstep(R * 5.0, R * 2.4, rd);
  float doppler = 0.55 + 0.45 * cos(ang + 0.4);
  vec3 hot = mix(vec3(1.0, 0.45, 0.12), vec3(1.0, 0.92, 0.75), swirl * doppler);
  float disc = band * (0.35 + 0.9 * swirl) * doppler;
  float front = step(0.0, -q.y) + step(0.0, q.y) * step(R * 1.05, r); // the near half crosses the hole
  col += hot * disc * front * 1.4;
  a = max(a, clamp(disc * front * 1.2, 0.0, 1.0));
  // the far side of the disc, lensed above the hole into a ring
  float ring = exp(-abs(r - R * 1.32) * 70.0) * (0.6 + 0.4 * fbm(vec2(atan(q.y, q.x) * 3.0 - t, t * 0.2)));
  col += vec3(1.0, 0.75, 0.45) * ring * 1.3;
  a = max(a, clamp(ring, 0.0, 1.0));
  // the horizon: black, with a thin glow
  float horizon = smoothstep(R * 1.02, R * 0.97, r);
  col *= 1.0 - horizon;
  a = max(a, horizon);
  float halo = exp(-max(r - R, 0.0) * 9.0) * 0.25;
  col += vec3(0.8, 0.4, 0.15) * halo * (1.0 - horizon);
  a = max(a, halo * (1.0 - horizon));
  gl_FragColor = vec4(col * a, a);
}`;

/** Underwater, looking up: the surface rippling at the top with the light breaking through it, rays
 * swaying down into the blue, depth darkening below. (Plankton and a school of fish are particles.) */
const REEF = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  // the surface, seen from below: bright cells of light, rippling
  vec2 s = vec2(p.x * 4.0, p.y * 9.0);
  float n = fbm(s + fbm(s * 0.8 + t * 0.35) * 1.5 + vec2(t * 0.1, 0.0));
  float cells = smoothstep(0.35, 0.8, n) * (0.7 + 0.3 * sin(p.x * 30.0 + n * 8.0 + t * 1.5));
  float surface = smoothstep(0.72, 0.96, uv.y);
  vec3 col = mix(vec3(0.05, 0.35, 0.55), vec3(0.75, 0.95, 1.0), cells) * surface;
  float a = surface * (0.45 + 0.5 * cells);
  // rays swaying down from the surface
  float sway = sin(t * 0.35) * 0.15;
  float rx = p.x + (1.0 - uv.y) * (0.25 + sway);
  float rays = pow(0.5 + 0.5 * sin(rx * 11.0 + sin(rx * 3.0 + t * 0.4) * 1.5), 4.0)
    * (0.5 + 0.5 * fbm(vec2(rx * 6.0, t * 0.2))) * smoothstep(0.1, 0.95, uv.y);
  col += vec3(0.5, 0.85, 1.0) * rays * 0.6 * (1.0 - surface);
  a = max(a, rays * 0.4 * (1.0 - surface));
  // depth: the blue thickening below
  float deep = smoothstep(0.7, 0.0, uv.y) * 0.35;
  col += vec3(0.0, 0.08, 0.18) * deep;
  a = max(a, deep);
  gl_FragColor = vec4(col * a, a);
}`;

/** A firestorm: flames bent by a strong wind, smoke rolling across the page lit orange from beneath.
 * (Embers and ash torn sideways are particles.) */
const FIRESTORM = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float gust = 0.6 + 0.3 * sin(t * 0.4) + 0.15 * sin(t * 1.3);
  // flames leaning with the wind
  vec2 q = vec2(p.x * 2.4 - uv.y * 1.6 * gust - t * 0.5, p.y * 1.7 - t * 1.3);
  vec2 warp = vec2(fbm(q * 1.3 + vec2(0.0, -t * 0.6)), fbm(q * 1.6 + vec2(5.2, -t * 0.9)));
  float n = fbm(q + warp * 1.8);
  float f = clamp((n * 1.5 + (0.25 - uv.y * 1.7) - 0.4) * 2.6, 0.0, 1.0);
  vec3 col = mix(vec3(0.45, 0.03, 0.0), vec3(1.0, 0.42, 0.04), smoothstep(0.05, 0.5, f));
  col = mix(col, vec3(1.0, 0.75, 0.3), smoothstep(0.55, 1.0, f));
  float a = smoothstep(0.02, 0.4, f) * 0.85;
  // smoke rolling to the side, thick and slow, lit from below
  vec2 r = vec2(p.x * 1.4 - t * 0.18 * gust, uv.y * 2.4);
  vec2 wr = vec2(fbm(r * 1.2 + t * 0.06), fbm(r * 1.2 + vec2(3.1, -t * 0.04)));
  float sm = fbm(r + wr * 2.0);
  float smoke = smoothstep(0.42, 0.85, sm) * smoothstep(0.2, 0.55, uv.y);
  vec3 grey = mix(vec3(0.1, 0.09, 0.09), vec3(0.32, 0.28, 0.27), sm);
  grey += vec3(0.55, 0.18, 0.03) * smoothstep(0.75, 0.25, uv.y) * smoothstep(0.42, 0.85, sm);
  col = mix(col, grey, smoke * (1.0 - smoothstep(0.1, 0.6, f)));
  a = max(a, smoke * 0.7);
  gl_FragColor = vec4(col * a, a);
}`;

/** A blizzard at night: veils of blown snow sweeping across in waves, gusts whitening the air for a
 * moment, a cold glow over the ground. (The flakes are particles in several depths.) */
const WHITEOUT = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float gust = smoothstep(0.55, 1.0, 0.5 + 0.35 * sin(t * 0.33) + 0.25 * sin(t * 0.91 + 1.0));
  vec2 q = vec2(p.x * 1.5 - t * 0.55, p.y * 2.0 + t * 0.12);
  vec2 w = vec2(fbm(q + t * 0.07), fbm(q + vec2(4.4, -t * 0.05)));
  float veil = fbm(q * 1.4 + w * 2.0);
  float drift = smoothstep(0.45, 0.9, veil) * (0.35 + 0.55 * gust);
  vec3 col = vec3(0.82, 0.88, 1.0);
  float a = drift * 0.55 + gust * 0.12;
  // the ground: a cold glow and snow streaming low
  float ground = smoothstep(0.25, 0.0, uv.y);
  float stream = fbm(vec2(p.x * 3.0 - t * 1.4, uv.y * 30.0));
  col = mix(col, vec3(0.6, 0.72, 0.95), ground * 0.5);
  a = max(a, ground * (0.25 + 0.35 * smoothstep(0.4, 0.8, stream)));
  gl_FragColor = vec4(col * a, a);
}`;

/** Liquid metal: a chrome surface flowing slowly, its relief catching a sky and sharp highlights, a
 * thin film of colour shimmering where it bends. */
const LIQUIDMETAL = `${COMMON}
float height(vec2 p, float t) {
  vec2 w = vec2(noise(p * 0.9 + t * 0.06), noise(p * 0.9 + vec2(5.2, -t * 0.05)));
  return noise(p * 1.4 + w * 2.0 + t * 0.04) * 0.75 + noise(p * 3.1 + w + t * 0.05) * 0.25;
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec2 q = p * 0.85;
  float e = 0.035;
  float h = height(q, t);
  vec3 n = normalize(vec3(height(q - vec2(e, 0.0), t) - height(q + vec2(e, 0.0), t),
                          height(q - vec2(0.0, e), t) - height(q + vec2(0.0, e), t), e * 1.4));
  vec3 view = vec3(0.0, 0.0, 1.0);
  vec3 rf = reflect(-view, n);
  // an environment: a cool sky above, a warm floor below, a bright strip of light
  vec3 env = mix(vec3(0.12, 0.13, 0.16), vec3(0.75, 0.8, 0.9), smoothstep(-0.4, 0.8, rf.y));
  env += vec3(1.0) * smoothstep(0.93, 1.0, dot(rf, normalize(vec3(0.4, 0.7, 0.6)))) * 1.2;
  vec3 film = 0.5 + 0.5 * cos(6.2831 * (h * 2.0 + vec3(0.0, 0.33, 0.67)) + t * 0.2);
  float edge = pow(1.0 - n.z, 1.5);
  vec3 col = env + film * edge * 0.45;
  float a = 0.3 + edge * 0.35;
  gl_FragColor = vec4(col * a, a);
}`;

/** A plasma storm: violet and cyan clouds of charged gas slowly folding, and electric arcs leaping
 * between drifting points — jagged, forked, each living a moment then fading, at random. */
const PLASMA = `${COMMON}
// distance to a jagged arc from a to b (coarse turns, fine crackle), and how far along it the point is
vec2 arc(vec2 p, vec2 a, vec2 b, float seed, float t) {
  vec2 ab = b - a;
  float len = length(ab);
  vec2 dir = ab / len;
  vec2 nrm = vec2(-dir.y, dir.x);
  float along = clamp(dot(p - a, dir) / len, 0.0, 1.0);
  float bend = (fbm(vec2(along * 3.0, seed + t * 0.6)) - 0.5) * 0.35 * len
    + (noise(vec2(along * 26.0, seed * 3.0 + t * 9.0)) - 0.5) * 0.035;
  float taper = sin(along * 3.14159);
  vec2 onArc = a + dir * along * len + nrm * bend * taper;
  return vec2(length(p - onArc), along);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  // the charged clouds
  vec2 q = p * 1.4;
  vec2 w = vec2(fbm(q + t * 0.035), fbm(q + vec2(3.3, -t * 0.03)));
  vec2 w2 = vec2(fbm(q * 1.6 + w * 1.5 + t * 0.02), fbm(q * 1.6 + w * 1.5 + vec2(7.1, 2.4)));
  float n = fbm(q + w2 * 1.8);
  vec3 gas = mix(vec3(0.22, 0.04, 0.42), vec3(0.08, 0.55, 0.85), smoothstep(0.3, 0.8, w2.y));
  gas = mix(gas, vec3(0.85, 0.4, 1.0), smoothstep(0.62, 0.92, n));
  o = over(o, gas, smoothstep(0.32, 0.85, n) * 0.6);
  // arcs: four at a time, each born at a random moment between two drifting anchors
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float life = 1.4 + hash(vec2(fi, 3.0)) * 1.6;
    float slot = floor((t + fi * 0.83) / life);
    float age = fract((t + fi * 0.83) / life);
    float alive = step(0.35, hash(vec2(slot, fi)));
    float env = alive * smoothstep(0.0, 0.06, age) * smoothstep(0.55, 0.15, age); // a strike, then a fade
    vec2 a = vec2(hash(vec2(slot, fi + 1.0)) * aspect, 0.2 + hash(vec2(slot, fi + 2.0)) * 0.7);
    vec2 b = a + (vec2(hash(vec2(slot, fi + 4.0)), hash(vec2(slot, fi + 5.0))) - 0.5) * vec2(0.9, 0.6);
    vec2 d = arc(p, a, b, slot * 7.0 + fi, t);
    float core = smoothstep(0.004, 0.0, d.x);
    float halo = exp(-d.x * 70.0) * 0.6;
    // a fork leaving the arc halfway
    vec2 mid = mix(a, b, 0.45);
    vec2 tip = mid + (vec2(hash(vec2(slot, fi + 6.0)), hash(vec2(slot, fi + 7.0))) - 0.5) * 0.35;
    vec2 f = arc(p, mid, tip, slot * 11.0 + fi, t);
    core += smoothstep(0.003, 0.0, f.x) * 0.8;
    halo += exp(-f.x * 90.0) * 0.4;
    float flick = 0.75 + 0.25 * noise(vec2(t * 25.0, fi));
    o = over(o, vec3(0.75, 0.6, 1.0), halo * env * flick);
    o = over(o, vec3(0.95, 0.97, 1.0), core * env * flick);
  }
  gl_FragColor = o;
}`;

/** A living forest: sunbeams slanting through the canopy, the shade of leaves stirring in the wind,
 * a mist breathing low. (Fireflies are particles.) */
const FOREST = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  // the canopy's shade: patches of foliage stirring in the wind
  vec2 l = p * 13.0 + vec2(sin(t * 0.3) * 0.4, cos(t * 0.23) * 0.3);
  vec2 sway = vec2(noise(l * 0.3 + t * 0.2), noise(l * 0.3 + vec2(4.0, t * 0.17))) * 1.2;
  float leaves = noise(l * 1.7 + sway) * 0.7 + noise(l * 3.4 + sway * 2.0) * 0.3;
  float canopy = smoothstep(0.35, 0.7, fbm(p * 1.6 + vec2(t * 0.02, 0.0)));
  float dapple = smoothstep(0.58, 0.72, leaves) * canopy * smoothstep(0.2, 1.0, uv.y);
  vec4 o = vec4(0.0);
  o = over(o, vec3(0.06, 0.16, 0.05), canopy * 0.3);
  o = over(o, vec3(0.75, 0.92, 0.45), dapple * 0.45);
  // sunbeams slanting from the top left: a few wide and soft, a few thin, slowly breathing
  float bx = p.x + uv.y * 0.6;
  float shafts = smoothstep(0.55, 1.0, sin(bx * 4.0 + sin(bx * 1.7) * 1.5))
    + 0.6 * smoothstep(0.85, 1.0, sin(bx * 11.0 + 1.3));
  float beams = shafts * (0.6 + 0.4 * sin(t * 0.4 + bx * 3.0)) * (0.7 + 0.3 * noise(vec2(bx * 3.0, t * 0.3)));
  beams *= smoothstep(0.0, 0.9, uv.y);
  // dust motes glittering in the beams
  vec2 mg = p * 90.0 + vec2(sin(t * 0.5) * 2.0, t * 1.5);
  float motes = step(0.988, hash(floor(mg))) * smoothstep(0.35, 0.0, length(fract(mg) - 0.5)) * beams;
  o = over(o, vec3(1.0, 0.93, 0.65), beams * 0.32);
  o = over(o, vec3(1.0, 1.0, 0.85), motes);
  // mist low over the ground
  float mist = fbm(vec2(p.x * 1.5 + t * 0.04, uv.y * 4.0 - t * 0.02)) * smoothstep(0.4, 0.0, uv.y);
  o = over(o, vec3(0.7, 0.8, 0.75), mist * 0.45);
  gl_FragColor = o;
}`;

/** A neon city in perspective: a ground of glowing roads between blocks of lit windows stretching to
 * the horizon, streams of data racing along the roads toward the viewer, a glitch tearing the image now
 * and then. */
const NEONCITY = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  float g = step(0.94, hash(vec2(floor(t * 3.0), 1.0)));
  float band = step(abs(uv.y - hash(vec2(floor(t * 3.0), 2.0)) * 0.6), 0.03);
  float x = p.x + g * band * (hash(vec2(floor(t * 3.0), 3.0)) - 0.5) * 0.15;
  // the ground plane, from the bottom of the page to a horizon two thirds up
  float horizon = 0.64;
  float depth = horizon - uv.y;
  if (depth <= 0.0) {
    float sky = smoothstep(horizon + 0.25, horizon, uv.y) * 0.25;
    gl_FragColor = vec4(vec3(0.6, 0.2, 0.8) * sky, sky);
    return;
  }
  float z = 0.35 / depth;
  vec2 c = vec2((x - aspect * 0.5) * z * 2.2, z + t * 0.9);
  vec2 cell = floor(c);
  vec2 f = fract(c);
  float wRoad = 0.06 + 0.04 * hash(cell);
  float lineW = fwidthApprox(z);
  float road = max(smoothstep(wRoad + lineW, wRoad, f.x), smoothstep(wRoad + lineW, wRoad, f.y));
  float px = fract(t * (0.3 + hash(vec2(cell.y, 5.0)) * 0.7) + hash(vec2(cell.y, 9.0)));
  float py = fract(-t * (0.6 + hash(vec2(cell.x, 6.0)) * 0.9) + hash(vec2(cell.x, 8.0)));
  float pulse = smoothstep(wRoad * 1.4, 0.0, f.y) * exp(-abs(f.x - px) * 12.0)
    + smoothstep(wRoad * 1.4, 0.0, f.x) * exp(-max(f.y - py, 0.0) * 6.0) * step(py - 0.02, f.y);
  vec2 win = floor(f * 6.0);
  float lit = step(0.7, hash(cell * 13.0 + win)) * step(0.14, f.x) * step(0.14, f.y);
  lit *= 0.6 + 0.4 * sin(t * 0.6 + hash(cell + win) * 30.0);
  vec3 tint = mix(vec3(0.0, 0.85, 1.0), vec3(1.0, 0.2, 0.75), step(0.5, hash(cell)));
  float fade = smoothstep(0.0, 0.18, depth);
  vec3 col = (tint * road * 0.6 + vec3(1.0, 0.95, 0.85) * pulse * 1.5 + tint * lit * 0.4) * fade;
  float a = clamp(road * 0.45 + pulse + lit * 0.35, 0.0, 1.0) * fade;
  col += vec3(0.4, 0.9, 1.0) * g * band * 0.4;
  a = max(a, g * band * 0.25);
  gl_FragColor = vec4(col * a, a);
}`;

/** Haunting: a light failing like a dying bulb, fog creeping along the floor, the dark closing in from
 * the edges to the rhythm of a heartbeat. (Pale wisps are particles.) */
const HAUNTED = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec4 o = vec4(0.0);
  // the heartbeat: two beats, a pause
  float beat = mod(t, 1.6);
  float pulse = exp(-beat * 9.0) + 0.7 * exp(-abs(beat - 0.28) * 12.0);
  // the dark closing in from the edges, tightening on each beat
  vec2 c = uv - 0.5;
  float vignette = smoothstep(0.12 - pulse * 0.06, 0.72, length(c * vec2(1.25, 1.0)));
  o = over(o, vec3(0.02, 0.0, 0.01), vignette * 0.95);
  // a shadow passing slowly across, now and then, like someone walking by a lamp
  float pass = mod(t, 13.0) / 4.0;
  float shadow = step(pass, 1.0) * smoothstep(0.35, 0.0, abs(uv.x - (pass * 1.6 - 0.3))) * 0.45;
  o = over(o, vec3(0.0), shadow);
  // a failing light: long dim stretches, sudden flickers
  float k = floor(t * 12.0);
  float failing = step(0.86, hash(vec2(k, 1.0))) * step(0.5, hash(vec2(floor(t * 0.7), 2.0)));
  o = over(o, vec3(0.75, 0.8, 0.7), failing * 0.14);
  o = over(o, vec3(0.0), (1.0 - failing) * step(0.97, hash(vec2(k, 3.0))) * 0.35);
  // fog creeping low, slow
  float fog = fbm(vec2(p.x * 1.4 + t * 0.03, uv.y * 3.5 - t * 0.015) + fbm(p * 2.0 + t * 0.02));
  fog *= smoothstep(0.55, 0.0, uv.y);
  o = over(o, vec3(0.55, 0.6, 0.62), smoothstep(0.3, 0.8, fog) * 0.7);
  // a red glow breathing with the heart, very faint
  o = over(o, vec3(0.35, 0.0, 0.02), pulse * vignette * 0.18);
  gl_FragColor = o;
}`;

/** Darkness: black tendrils creeping in from the edges, red veins pulsing inside them, and eyes opening
 * in the dark — pairs of red embers that blink, then close. */
const DARKNESS = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  // how far in from the nearest edge, wavering
  float edge = min(min(uv.x, 1.0 - uv.x), min(uv.y, 1.0 - uv.y));
  float creep = fbm(p * 3.0 + vec2(t * 0.05, -t * 0.04));
  float reach = 0.08 + 0.06 * sin(t * 0.2) + creep * 0.16;
  float dark = smoothstep(reach, reach - 0.12, edge);
  // tendrils: ridged noise reaching inward
  float ridge = 1.0 - abs(fbm(p * 5.0 + vec2(-t * 0.08, t * 0.06)) * 2.0 - 1.0);
  float tendril = smoothstep(0.75, 0.95, ridge) * smoothstep(reach + 0.2, reach - 0.05, edge);
  o = over(o, vec3(0.0), max(dark, tendril) * 0.92);
  // red veins pulsing inside the dark
  float vein = smoothstep(0.012, 0.0, abs(fbm(p * 7.0 + t * 0.03) - 0.5))
    * smoothstep(reach + 0.05, reach - 0.1, edge);
  float throb = 0.5 + 0.5 * sin(t * 2.4);
  o = over(o, vec3(0.6, 0.02, 0.03), vein * (0.4 + 0.5 * throb));
  // eyes: a pair now and then, somewhere in the dark, opening, blinking, closing
  float slot = floor(t / 4.0);
  float ph = mod(t, 4.0);
  vec2 at = vec2(hash(vec2(slot, 1.0)), hash(vec2(slot, 2.0)));
  at = vec2(at.x < 0.5 ? 0.06 + at.x * 0.2 : 0.74 + at.x * 0.2, 0.15 + at.y * 0.7);
  vec2 e = vec2((uv.x - at.x) * aspect, uv.y - at.y);
  float open = smoothstep(0.0, 0.6, ph) * smoothstep(3.6, 3.0, ph) * step(0.08, abs(ph - 1.9));
  float gap = 0.022;
  float eyes = 0.0;
  for (int i = 0; i < 2; i++) {
    vec2 d = e - vec2(i == 0 ? -gap : gap, 0.0);
    eyes += smoothstep(0.009, 0.0, length(d * vec2(1.0, 1.0 / max(open, 0.05)))) ;
  }
  float glow = exp(-length(e) * 40.0) * 0.5;
  o = over(o, vec3(1.0, 0.12, 0.05), (eyes + glow) * open * step(0.35, hash(vec2(slot, 4.0))));
  gl_FragColor = o;
}`;

/** Lost signal: a found-footage tape — grain crawling over everything, a bright tear rolling down, the
 * colours split, and now and then the picture cutting to black. */
const LOSTSIGNAL = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec4 o = vec4(0.0);
  // grain: fine, changing every frame
  float grain = hash(floor(gl_FragCoord.xy * 0.6) + floor(t * 24.0) * 17.0);
  o = over(o, vec3(grain), 0.2);
  // jitter: thin lines torn sideways, now and then
  float jitter = step(0.96, hash(vec2(floor(gl_FragCoord.y / 3.0), floor(t * 15.0))));
  o = over(o, vec3(0.85), jitter * 0.35);
  // a tear rolling down the picture, the lines around it shifting
  float roll = fract(t * 0.11);
  float near = exp(-abs(uv.y - (1.0 - roll)) * 60.0);
  float lines = step(0.5, fract(gl_FragCoord.y * 0.5)) * 0.06;
  o = over(o, vec3(0.9), near * 0.5 + lines * 0.5);
  // split colours along the tear
  float shift = near * (hash(vec2(floor(t * 20.0), uv.y)) - 0.5);
  o = over(o, vec3(1.0, 0.1, 0.2), smoothstep(0.0, 0.3, abs(shift)) * 0.25);
  o = over(o, vec3(0.1, 0.9, 1.0), smoothstep(0.0, 0.3, abs(shift * 1.3)) * 0.18);
  // the edges of an old screen, darker
  vec2 c = uv - 0.5;
  o = over(o, vec3(0.0), smoothstep(0.3, 0.72, length(c)) * 0.75);
  // now and then the picture cuts to black, a timecode blinking
  float cut = step(0.93, hash(vec2(floor(t * 1.5), 7.0)));
  o = over(o, vec3(0.0), cut * 0.75);
  gl_FragColor = o;
}`;

/** String lights: strings of warm bulbs sagging across the top of the page, each bulb glowing in its
 * own colour and twinkling at its own pace. (Snow falls as particles.) */
const GARLAND = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  for (int s = 0; s < 3; s++) {
    float fs = float(s);
    float span = 0.55 + fs * 0.1;
    float x = p.x / span + fs * 0.37;
    float sag = 0.07 + 0.02 * fs;
    float y0 = 0.94 - fs * 0.11 - sag * 4.0 * fract(x) * (1.0 - fract(x));
    float wire = smoothstep(0.0025, 0.0, abs(uv.y - y0));
    o = over(o, vec3(0.08, 0.12, 0.08), wire * 0.8);
    // bulbs along the wire
    float n = 9.0;
    float bi = floor(fract(x) * n);
    float bx = (bi + 0.5) / n;
    float id = floor(x) * 10.0 + bi + fs * 100.0;
    float by = 0.94 - fs * 0.11 - sag * 4.0 * bx * (1.0 - bx) - 0.012;
    vec2 d = vec2((fract(x) - bx) * span, uv.y - by);
    float r = length(d);
    float tw = 0.55 + 0.45 * sin(t * (1.0 + hash(vec2(id, 1.0)) * 2.5) + id);
    vec3 hue = 0.55 + 0.45 * cos(6.2831 * (hash(vec2(id, 2.0)) + vec3(0.0, 0.33, 0.67)));
    hue = mix(hue, vec3(1.0, 0.8, 0.45), 0.35);
    o = over(o, hue, smoothstep(0.009, 0.004, r) * (0.6 + 0.4 * tw));
    o = over(o, hue, exp(-r * 60.0) * 0.6 * tw);
  }
  gl_FragColor = o;
}`;

/** Christmas night: a winter sky of stars over snowy fir trees, the moon glowing, and now and then a
 * sleigh with its reindeer crossing in front of it. (Snow falls as particles.) */
const CHRISTMASNIGHT = `${COMMON}
float fir(vec2 p, float x0, float h, float w) {
  // a fir tree: stacked triangles, its snowy edges
  float y = p.y;
  float half_ = w * (1.0 - y / h) * (0.75 + 0.25 * fract(y / h * 4.0));
  return step(y, h) * step(abs(p.x - x0), half_);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, vec3(0.04, 0.08, 0.2), smoothstep(0.2, 1.0, uv.y) * 0.45);
  vec2 sg = p * 120.0;
  float sh = hash(floor(sg));
  float star = step(0.994, sh) * smoothstep(0.45, 0.0, length(fract(sg) - 0.5)) * (0.5 + 0.5 * sin(t * 2.0 + sh * 70.0));
  o = over(o, vec3(1.0, 0.97, 0.88), star * smoothstep(0.3, 0.6, uv.y));
  // the moon and its glow
  vec2 moon = vec2(aspect * 0.78, 0.76);
  float dm = length(p - moon);
  o = over(o, vec3(0.95, 0.95, 0.85), exp(-dm * 9.0) * 0.35);
  o = over(o, vec3(1.0, 0.98, 0.9), smoothstep(0.072, 0.066, dm));
  // a sleigh crossing the moon, now and then: a silhouette with its reindeer
  float pass = mod(t, 22.0) / 6.0;
  float sx = moon.x - 0.45 + pass * 0.9;
  vec2 q = p - vec2(sx, moon.y - 0.01 + sin(pass * 3.0) * 0.01);
  float sleigh = smoothstep(1.0, 0.8, length(q / vec2(0.03, 0.009)));
  sleigh += smoothstep(0.0025, 0.0, abs(q.y + 0.011)) * step(abs(q.x), 0.032); // the runner
  for (int i = 1; i < 5; i++) {
    float fi = float(i);
    vec2 r = q - vec2(0.04 + fi * 0.028, 0.012 + sin(t * 8.0 + fi) * 0.003);
    sleigh += smoothstep(1.0, 0.75, length(r / vec2(0.011, 0.0055)));             // body
    sleigh += smoothstep(1.0, 0.7, length((r - vec2(0.011, 0.006)) / vec2(0.004, 0.0035))); // head
    sleigh += smoothstep(0.0012, 0.0, abs(r.x - 0.012)) * step(abs(r.y - 0.012), 0.004); // antlers
    sleigh += smoothstep(0.001, 0.0, abs(abs(r.x) - 0.006)) * step(abs(r.y + 0.008), 0.004); // legs
  }
  o = over(o, vec3(0.02, 0.03, 0.06), clamp(sleigh, 0.0, 1.0) * step(pass, 1.0));
  // snowy hills and firs
  float hill = 0.12 + 0.04 * sin(p.x * 2.0) + 0.02 * sin(p.x * 5.3 + 1.0);
  float ground = step(p.y, hill);
  float trees = 0.0;
  for (int i = 0; i < 9; i++) {
    float fi = float(i);
    float x0 = (fi + 0.3 * hash(vec2(fi, 1.0))) / 9.0 * aspect;
    float h = 0.16 + 0.12 * hash(vec2(fi, 2.0));
    trees += fir(vec2(p.x, p.y - hill + 0.01), x0, h, 0.045 + 0.02 * hash(vec2(fi, 3.0)));
  }
  trees = clamp(trees, 0.0, 1.0);
  o = over(o, vec3(0.02, 0.06, 0.05), trees);
  o = over(o, vec3(0.75, 0.82, 0.95), ground * 0.9);
  // snow on the hills sparkling
  float sparkle = step(0.997, hash(floor(p * 200.0) + floor(t * 3.0))) * ground;
  o = over(o, vec3(1.0), sparkle);
  gl_FragColor = o;
}`;

/** By the fire: the warm glow of a hearth breathing at the bottom of the page, and frost creeping from
 * the corners of the window, branching like ice crystals. (Embers crackle as particles.) */
const HEARTH = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec4 o = vec4(0.0);
  float breathe = 0.75 + 0.15 * sin(t * 1.7) + 0.1 * noise(vec2(t * 3.0, 0.0));
  float glow = smoothstep(0.65, 0.0, uv.y) * breathe;
  o = over(o, vec3(0.9, 0.38, 0.08), glow * 0.3);
  // low flames licking at the very bottom
  vec2 q = vec2(p.x * 4.0, p.y * 3.0 - t * 1.6);
  float f = clamp((fbm(q + fbm(q * 1.4 - t * 0.6)) * 1.5 + (0.1 - uv.y * 3.5) - 0.35) * 2.5, 0.0, 1.0);
  o = over(o, mix(vec3(0.9, 0.25, 0.02), vec3(1.0, 0.75, 0.3), f), smoothstep(0.05, 0.5, f) * 0.85);
  // frost from the corners: branching crystals growing and melting slowly
  vec2 c = min(uv, 1.0 - uv) * vec2(u_res.x / u_res.y, 1.0);
  float corner = length(c);
  float grow = 0.3 + 0.04 * sin(t * 0.15);
  float crystal = 1.0 - abs(fbm(p * 26.0) * 2.0 - 1.0);
  float reach = smoothstep(grow, grow * 0.35, corner);
  o = over(o, vec3(0.75, 0.85, 0.95), reach * 0.18); // a misted pane
  float lines = smoothstep(0.9, 0.985, crystal) + 0.6 * smoothstep(0.93, 0.99, 1.0 - abs(fbm(p * 55.0) * 2.0 - 1.0));
  o = over(o, vec3(0.92, 0.97, 1.0), lines * reach * 0.75);
  gl_FragColor = o;
}`;

export const SHADERS: Record<string, string> = {
  haunted: HAUNTED,
  darkness: DARKNESS,
  lostsignal: LOSTSIGNAL,
  garland: GARLAND,
  christmasnight: CHRISTMASNIGHT,
  hearth: HEARTH,
  volcano: VOLCANO,
  blackhole: BLACKHOLE,
  reef: REEF,
  firestorm: FIRESTORM,
  whiteout: WHITEOUT,
  liquidmetal: LIQUIDMETAL,
  plasma: PLASMA,
  forest: FOREST,
  neoncity: NEONCITY,
  matrix: MATRIX,
  inferno: INFERNO,
  thunderstorm: THUNDERSTORM,
  sandstorm: SANDSTORM,
  polar: POLAR,
  cosmos: COSMOS,
  abyss: ABYSS,
  downpour: DOWNPOUR,
};
