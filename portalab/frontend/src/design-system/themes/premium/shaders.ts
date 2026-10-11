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

/** A volcano: a field of lava — glowing veins cracking a dark crust, flowing slowly, pulsing — a crater
 * glowing below an ash plume lit red from beneath; eruptions at random moments throwing lava bombs on
 * real arcs; volcanic lightning crackling in the plume; the air shimmering over the heat. (Ash and sparks
 * are particles.) */
const VOLCANO = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  vec2 vent = vec2(aspect * 0.68, 0.42);
  // eruptions: some slots erupt, the glow surges with them
  float slot = floor(t / 3.5);
  float ph = mod(t, 3.5);
  float erupting = step(0.45, hash(vec2(slot, 1.0)));
  float surge = erupting * exp(-ph * 1.2);
  // the air shimmering above the lava
  vec2 shimmer = vec2(noise(vec2(p.x * 9.0, uv.y * 14.0 - t * 2.5)) - 0.5, 0.0) * 0.012 * smoothstep(0.5, 0.15, uv.y);
  vec2 pw = p + shimmer;
  // the plume: ash billowing up from the vent, lit red from below, crackling with lightning
  vec2 r = vec2((pw.x - vent.x) * 1.5, uv.y * 1.9 - t * 0.12);
  vec2 wr = vec2(fbm(r + t * 0.05), fbm(r + vec2(6.1, 2.3)));
  float ash = fbm(r * 1.3 + wr * 2.2);
  float column = smoothstep(0.1 + (uv.y - vent.y) * 1.2, 0.0, abs(pw.x - vent.x - (uv.y - vent.y) * 0.35))
    * smoothstep(vent.y - 0.02, vent.y + 0.04, uv.y);
  float plume = (smoothstep(0.22, 0.7, ash) + smoothstep(0.35, 0.0, uv.y - vent.y) * 0.45) * column;
  vec3 smoke = mix(vec3(0.26, 0.22, 0.21), vec3(0.6, 0.54, 0.52), ash);
  smoke += vec3(0.85, 0.2, 0.03) * smoothstep(vent.y + 0.35, vent.y, uv.y) * (0.45 + 0.6 * surge + 0.15 * sin(t * 1.3));
  o = over(o, smoke, clamp(plume, 0.0, 1.0) * 0.92);
  // volcanic lightning inside the plume
  float bslot = floor(t / 1.3);
  float bph = mod(t, 1.3);
  float strike = step(0.72, hash(vec2(bslot, 5.0))) * exp(-bph * 8.0);
  vec2 bAt = vent + vec2((hash(vec2(bslot, 6.0)) - 0.5) * 0.3, 0.25 + hash(vec2(bslot, 7.0)) * 0.3);
  float bx = bAt.x + (fbm(vec2(uv.y * 9.0, bslot)) - 0.5) * 0.12;
  float bolt = smoothstep(0.004, 0.0, abs(pw.x - bx)) * step(abs(uv.y - bAt.y), 0.09);
  o = over(o, vec3(0.75, 0.8, 1.0), clamp(bolt * 2.0 + exp(-length(pw - bAt) * 12.0) * 0.5, 0.0, 1.0) * strike);
  // the lava field
  vec2 q = vec2(pw.x * 3.0 + t * 0.04, uv.y * 7.0 - t * 0.05);
  vec2 w = vec2(fbm(q * 0.7 + t * 0.03), fbm(q * 0.7 + vec2(3.7, -t * 0.02)));
  float n = fbm(q + w * 1.6);
  float vein = smoothstep(0.06, 0.0, abs(n - 0.5)) + 0.5 * smoothstep(0.15, 0.0, abs(n - 0.5));
  float pulse = 0.75 + 0.25 * sin(t * 1.3 + n * 9.0) + 0.3 * surge;
  float field = smoothstep(0.3, 0.06, uv.y);
  vec3 lava = mix(vec3(0.9, 0.18, 0.02), vec3(1.0, 0.78, 0.3), clamp(vein - 0.4, 0.0, 1.0)) * pulse;
  vec3 crust = vec3(0.07, 0.03, 0.02) + vec3(0.22, 0.05, 0.0) * fbm(q * 3.0);
  o = over(o, mix(crust, lava, clamp(vein, 0.0, 1.0)), field * (0.6 + 0.4 * clamp(vein, 0.0, 1.0)));
  // the mountain: a dark cone up to the crater, lava streams running down its slopes
  float slope = vent.y - abs(pw.x - vent.x) * (0.62 + 0.08 * noise(vec2(pw.x * 6.0, 1.0)));
  float rough = (fbm(vec2(pw.x * 8.0, 3.0)) - 0.5) * 0.05;
  float mountain = smoothstep(0.004, -0.004, uv.y - slope - rough) * step(0.0, slope);
  vec3 rock = vec3(0.06, 0.04, 0.04) + vec3(0.09, 0.04, 0.03) * fbm(pw * 12.0);
  float stream = smoothstep(0.03, 0.0, abs(fbm(vec2(pw.x * 4.0, uv.y * 3.0 + t * 0.08)) - 0.5))
    * smoothstep(slope + 0.01, slope - 0.25, uv.y) * smoothstep(0.42, 0.05, abs(pw.x - vent.x));
  vec3 slopeCol = mix(rock, vec3(1.0, 0.45, 0.08) * pulse, clamp(stream * 1.5, 0.0, 1.0));
  o = over(o, slopeCol, mountain * 0.95);
  // the crater glowing
  float crater = exp(-length((pw - vent) * vec2(1.0, 3.0)) * 9.0);
  o = over(o, vec3(1.0, 0.5, 0.1), crater * (0.55 + 0.45 * surge));
  // lava bombs: thrown on arcs, cooling as they fly, a short glowing trail
  for (int i = 0; i < 10; i++) {
    float fi = float(i);
    float age = ph - hash(vec2(slot, fi + 20.0)) * 0.6;
    if (age < 0.0 || age > 2.4) continue;
    vec2 v0 = vec2((hash(vec2(slot, fi + 30.0)) - 0.5) * 0.5, 0.45 + hash(vec2(slot, fi + 40.0)) * 0.45);
    vec2 at = vent + v0 * age - vec2(0.0, 0.32) * age * age;
    vec2 back = vent + v0 * (age - 0.06) - vec2(0.0, 0.32) * (age - 0.06) * (age - 0.06);
    vec2 pa = pw - back;
    vec2 ba = at - back;
    float h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-6), 0.0, 1.0);
    float trail = smoothstep(0.004, 0.0, length(pa - ba * h)) * h;
    float bomb = smoothstep(0.006, 0.0, length(pw - at));
    vec3 hot = mix(vec3(1.0, 0.85, 0.4), vec3(0.9, 0.2, 0.02), age / 2.4);
    o = over(o, hot, clamp(bomb + trail * 0.7, 0.0, 1.0) * erupting * step(0.05, at.y));
  }
  float glow = smoothstep(0.55, 0.08, uv.y) * 0.22 * pulse;
  o = over(o, vec3(0.7, 0.12, 0.0), glow);
  gl_FragColor = o;
}`;

/** A black hole: a thin accretion disc swirling in spiral streaks, hotter and whiter toward the hole,
 * brighter and bluer on the side turning toward us; its far side lensed into arcs above and below the
 * shadow, a hair-thin photon ring around it; the starry sky bent around the hole into an Einstein ring;
 * and now and then a star caught, whirling faster as it falls, stretched into a streak, flaring out. */
const BLACKHOLE = `${COMMON}
float starField(vec2 p, float scale, float threshold) {
  vec2 g = p * scale;
  vec2 id = floor(g);
  vec2 f = fract(g) - 0.5 - (vec2(hash(id + 3.1), hash(id + 7.7)) - 0.5) * 0.6;
  return step(threshold, hash(id)) * smoothstep(0.09, 0.0, length(f)) * (0.35 + 0.65 * hash(id + 1.3));
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec2 c = vec2(aspect * 0.66, 0.55);
  vec2 q = p - c;
  float r = length(q);
  float R = 0.07;
  vec2 dir = q / max(r, 0.0001);
  vec4 o = vec4(0.0);
  // the sky, bent around the hole; an Einstein ring where the bending focuses it
  vec2 sky = c + dir * max(r - R * R * 2.2 / max(r, 0.001), 0.0);
  float focus = 1.0 + 2.5 * exp(-abs(r - R * 1.6) * 30.0);
  float neb = fbm(sky * 2.0 + vec2(t * 0.004, 0.0));
  o = over(o, mix(vec3(0.12, 0.05, 0.22), vec3(0.18, 0.1, 0.32), neb), smoothstep(0.45, 0.85, neb) * 0.25);
  float stars = starField(sky + vec2(t * 0.002, 0.0), 70.0, 0.984) + starField(sky * 1.7 + 3.0, 115.0, 0.99) * 0.7;
  stars *= 0.75 + 0.25 * sin(t * 2.0 + hash(floor(sky * 70.0)) * 40.0);
  o = over(o, vec3(0.9, 0.93, 1.0), clamp(stars * focus, 0.0, 1.0) * smoothstep(R * 1.05, R * 1.45, r));
  // the disc, in its tilted plane: spiral streaks, faster near the hole
  float tilt = 3.6;
  vec2 d = vec2(q.x, q.y * tilt);
  float rd = length(d);
  float ang = atan(d.y, d.x);
  float spin = t * 1.6 * pow(R / max(rd, R), 1.5);
  float spiral = ang - spin * 6.0 + log(rd) * 3.2;
  float streak = fbm(vec2(spiral * 2.4, rd * 28.0));
  float fine = noise(vec2(spiral * 14.0, rd * 90.0));
  float inner = R * 1.55;
  float band = smoothstep(inner, inner * 1.1, rd) * smoothstep(R * 5.6, inner * 2.1, rd);
  float heat = pow(clamp(inner / rd, 0.0, 1.0), 1.6);
  float facing = 0.5 + 0.5 * cos(ang + 0.35);
  float beam = 0.35 + 1.35 * facing * facing;
  vec3 disc = mix(vec3(0.82, 0.22, 0.05), vec3(1.0, 0.62, 0.25), heat);
  disc = mix(disc, vec3(1.0, 0.96, 0.88), heat * heat * beam * 0.8);
  disc *= mix(vec3(1.0), vec3(0.82, 0.92, 1.2), smoothstep(0.7, 1.5, beam));
  float density = band * (0.22 + 0.78 * streak) * (0.65 + 0.35 * fine);
  float hidden = step(0.0, q.y) * step(r, R * 1.1);
  // the far side of the disc, lensed over the top of the shadow (and a thin arc under it)
  float top = exp(-abs(r - R * 1.78) * 50.0) * smoothstep(-0.25, 0.65, dir.y);
  float bottom = exp(-abs(r - R * 1.3) * 85.0) * smoothstep(0.1, -0.6, dir.y) * 0.55;
  float arcs = (top + bottom) * (0.55 + 0.45 * fbm(vec2(atan(q.y, q.x) * 4.0 - t * 0.9, t * 0.1)));
  o = over(o, vec3(1.0, 0.7, 0.35), clamp(arcs, 0.0, 1.0) * 0.9);
  o = over(o, vec3(0.0), smoothstep(R * 1.02, R * 0.95, r));
  o = over(o, disc, clamp(density * beam * 1.25, 0.0, 1.0) * (1.0 - hidden));
  o = over(o, vec3(1.0, 0.87, 0.65), exp(-abs(r - R * 1.07) * 170.0) * 0.85);
  // stars caught: a few, at random, falling in a tightening whirl, stretched, flaring at the end
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float life = 7.0 + hash(vec2(fi, 1.0)) * 5.0;
    float k = floor((t + fi * 3.1) / life);
    float ph = fract((t + fi * 3.1) / life);
    float caught = step(0.35, hash(vec2(k, fi + 9.0)));
    float r0 = 0.32 + 0.25 * hash(vec2(k, fi + 2.0));
    float a0 = hash(vec2(k, fi + 3.0)) * 6.2831;
    float rr = mix(r0, R * 1.1, pow(ph, 1.7));
    float aa = a0 + ph * 3.0 + pow(ph, 3.0) * 11.0;
    vec2 sp = c + vec2(cos(aa), sin(aa) / tilt * 1.5) * rr;
    vec2 tang = normalize(vec2(-sin(aa), cos(aa) / tilt * 1.5));
    vec2 dd = p - sp;
    float along = dot(dd, tang);
    float across = dot(dd, vec2(-tang.y, tang.x));
    float tail = 0.004 + 0.055 * pow(ph, 3.0);
    float body = exp(-pow(across / 0.0024, 2.0))
      * exp(-pow(max(along, 0.0) / 0.004, 2.0) - pow(min(along, 0.0) / tail, 2.0));
    float flare = exp(-length(dd) * 110.0) * smoothstep(0.86, 1.0, ph);
    float fade = smoothstep(0.0, 0.1, ph) * smoothstep(1.0, 0.96, ph);
    o = over(o, vec3(0.85, 0.92, 1.0), clamp(body * 1.2 + flare, 0.0, 1.0) * fade * caught);
  }
  gl_FragColor = o;
}`;

/** Underwater, looking up: the surface rippling with the light breaking through it, rays swaying down,
 * caustics dancing on the depths, a jellyfish drifting and pulsing, translucent, trailing its threads.
 * (Plankton and a school of fish are particles.) */
const REEF = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, vec3(0.0, 0.07, 0.16), smoothstep(0.75, 0.0, uv.y) * 0.4);
  // the surface seen from below
  vec2 sfc = vec2(p.x * 4.0, p.y * 9.0);
  float n = fbm(sfc + fbm(sfc * 0.8 + t * 0.35) * 1.5 + vec2(t * 0.1, 0.0));
  float cells = smoothstep(0.35, 0.8, n) * (0.7 + 0.3 * sin(p.x * 30.0 + n * 8.0 + t * 1.5));
  float surface = smoothstep(0.72, 0.96, uv.y);
  o = over(o, mix(vec3(0.05, 0.35, 0.55), vec3(0.75, 0.95, 1.0), cells), surface * (0.45 + 0.5 * cells));
  // rays swaying down
  float rx = p.x + (1.0 - uv.y) * (0.25 + sin(t * 0.35) * 0.15);
  float rays = pow(0.5 + 0.5 * sin(rx * 11.0 + sin(rx * 3.0 + t * 0.4) * 1.5), 4.0)
    * (0.5 + 0.5 * fbm(vec2(rx * 6.0, t * 0.2))) * smoothstep(0.1, 0.95, uv.y);
  o = over(o, vec3(0.5, 0.85, 1.0), rays * 0.38 * (1.0 - surface));
  // caustics on the depths
  vec2 cw = vec2(noise(p * 3.0 + t * 0.3), noise(p * 3.0 + vec2(4.0, -t * 0.25)));
  float cn = noise(p * 11.0 + cw * 2.2) * 0.7 + noise(p * 23.0 + cw * 3.0 + t * 0.2) * 0.3;
  float caustic = smoothstep(0.58, 0.78, cn) * smoothstep(0.32, 0.0, uv.y);
  o = over(o, vec3(0.45, 0.85, 1.0), caustic * 0.4);
  // a jellyfish: a bell that contracts and relaxes, drifting up and sideways, its threads trailing
  float cycle = 34.0;
  float life = mod(t, cycle) / cycle;
  vec2 jp = vec2(aspect * (0.15 + 0.7 * life), 0.25 + 0.4 * life + 0.03 * sin(t * 0.7));
  float beat = 0.5 + 0.5 * sin(t * 2.2);
  vec2 jq = p - jp;
  vec2 bellR = vec2(0.055 + 0.012 * beat, 0.04 - 0.008 * beat);
  float bellD = length(jq / bellR);
  float bell = smoothstep(1.0, 0.85, bellD) * step(-0.004, jq.y);
  float rim = smoothstep(0.12, 0.0, abs(bellD - 0.95)) * step(-0.004, jq.y);
  float threads = 0.0;
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    float x0 = (fi - 2.0) * 0.018;
    float y = -jq.y;
    float wave = sin(y * 40.0 - t * 3.0 + fi) * 0.008 * (y / 0.15);
    threads += smoothstep(0.0022, 0.0, abs(jq.x - x0 - wave)) * step(0.0, y) * smoothstep(0.17, 0.02, y);
  }
  vec3 jelly = vec3(0.75, 0.6, 1.0);
  o = over(o, jelly, bell * 0.18 + rim * 0.55);
  o = over(o, jelly * 1.1, threads * 0.45);
  o = over(o, vec3(0.9, 0.8, 1.0), exp(-length(jq) * 30.0) * 0.25 * (0.6 + 0.4 * beat));
  gl_FragColor = o;
}`;

/** A firestorm: a line of trees burning on the horizon, flames bent by a gusting wind and flaring up
 * with the gusts, smoke rolling across the page lit orange from beneath. (Embers and ash torn sideways
 * are particles.) */
const FIRESTORM = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float gust = 0.55 + 0.3 * sin(t * 0.4) + 0.15 * sin(t * 1.3) + 0.25 * smoothstep(0.7, 1.0, noise(vec2(t * 0.5, 2.0)));
  vec4 o = vec4(0.0);
  // smoke rolling to the side, thick and slow, lit from below
  vec2 r = vec2(p.x * 1.4 - t * 0.2 * gust, uv.y * 2.4);
  vec2 wr = vec2(fbm(r * 1.2 + t * 0.06), fbm(r * 1.2 + vec2(3.1, -t * 0.04)));
  float sm = fbm(r + wr * 2.0);
  float smoke = smoothstep(0.4, 0.85, sm) * smoothstep(0.25, 0.6, uv.y);
  vec3 grey = mix(vec3(0.12, 0.1, 0.1), vec3(0.36, 0.31, 0.3), sm);
  grey += vec3(0.6, 0.2, 0.04) * smoothstep(0.75, 0.3, uv.y) * smoothstep(0.4, 0.85, sm) * gust;
  o = over(o, grey, smoke * 0.72);
  // the burning treeline: trunks and crowns in silhouette against the fire
  float trees = 0.0;
  for (int i = 0; i < 14; i++) {
    float fi = float(i);
    float x0 = (fi + hash(vec2(fi, 1.0)) * 0.6) / 14.0 * u_res.x / u_res.y;
    float h = 0.16 + 0.1 * hash(vec2(fi, 2.0));
    float lean = (uv.y - 0.08) * 0.12 * gust;
    float y = (uv.y - 0.08) / h;
    // a fir: tiers of jagged branches narrowing to the top
    float tier = fract(y * 5.0);
    float w = (0.05 + 0.02 * hash(vec2(fi, 3.0))) * (1.0 - y) * (0.65 + 0.35 * (1.0 - tier));
    w *= 0.75 + 0.5 * noise(vec2(uv.y * 90.0, fi * 7.0));
    trees += smoothstep(0.003, 0.0, abs(p.x - x0 - lean) - max(w, 0.0)) * step(0.08, uv.y) * step(uv.y, 0.08 + h);
    trees += step(abs(p.x - x0), 0.005) * step(uv.y, 0.1);
  }
  // flames behind and among the trees, leaning with the wind
  vec2 q = vec2(p.x * 2.4 - uv.y * 1.6 * gust - t * 0.5, p.y * 1.7 - t * 1.3);
  vec2 warp = vec2(fbm(q * 1.3 + vec2(0.0, -t * 0.6)), fbm(q * 1.6 + vec2(5.2, -t * 0.9)));
  float n = fbm(q + warp * 1.8) + (1.0 - abs(noise(vec2(p.x * 10.0, p.y * 3.0 - t * 2.6)) * 2.0 - 1.0)) * 0.15;
  float f = clamp((n * 1.5 + (0.24 - uv.y * 1.8) - 0.4 + gust * 0.08) * 2.6, 0.0, 1.0);
  vec3 fire = mix(vec3(0.45, 0.03, 0.0), vec3(1.0, 0.4, 0.04), smoothstep(0.05, 0.5, f));
  fire = mix(fire, vec3(1.0, 0.72, 0.3), smoothstep(0.65, 1.0, f));
  fire *= 0.7 + 0.45 * fbm(q * 3.0 + t);
  o = over(o, fire, smoothstep(0.02, 0.4, f) * 0.85);
  o = over(o, vec3(0.03, 0.01, 0.0), clamp(trees, 0.0, 1.0) * 0.92);
  o = over(o, vec3(0.8, 0.25, 0.02), smoothstep(0.5, 0.0, uv.y) * 0.15 * gust);
  gl_FragColor = o;
}`;

/** A blizzard at night: veils of blown snow sweeping across in waves, gusts whitening the air for a
 * moment, a road of streetlamps whose halos light the snow racing through them, a cold glow over the
 * ground. (The flakes are particles in several depths.) */
const WHITEOUT = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  float gust = smoothstep(0.55, 1.0, 0.5 + 0.35 * sin(t * 0.33) + 0.25 * sin(t * 0.91 + 1.0));
  // streetlamps receding along a road, each lighting a cone of snow streaming through it
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float x0 = aspect * (0.12 + fi * 0.26);
    float top = 0.62 - fi * 0.05;
    float size = 1.0 - fi * 0.18;
    vec2 lamp = vec2(x0, top);
    o = over(o, vec3(0.05, 0.06, 0.08), step(abs(p.x - x0), 0.004 * size) * step(uv.y, top) * step(0.12, uv.y));
    float cone = smoothstep(0.18 * size, 0.0, abs(p.x - x0) - (top - uv.y) * 0.35) * step(uv.y, top) * step(0.08, uv.y);
    float snowIn = 0.5 + 0.5 * fbm(vec2(p.x * 18.0 - t * 4.0, uv.y * 30.0 + t * 2.0));
    o = over(o, vec3(1.0, 0.85, 0.55), cone * 0.32 * snowIn * size);
    o = over(o, vec3(1.0, 0.88, 0.6), clamp(exp(-length((p - lamp) * vec2(1.0, 1.3)) * 16.0) * 1.1, 0.0, 1.0) * size);
  }
  // veils of blown snow
  vec2 q = vec2(p.x * 1.5 - t * 0.55, p.y * 2.0 + t * 0.12);
  vec2 w = vec2(fbm(q + t * 0.07), fbm(q + vec2(4.4, -t * 0.05)));
  float veil = fbm(q * 1.4 + w * 2.0);
  float drift = smoothstep(0.45, 0.9, veil) * (0.35 + 0.55 * gust);
  o = over(o, vec3(0.82, 0.88, 1.0), drift * 0.55 + gust * 0.1);
  // the ground: a cold glow and snow streaming low
  float ground = smoothstep(0.14, 0.0, uv.y);
  float stream = fbm(vec2(p.x * 3.0 - t * 1.4, uv.y * 30.0));
  o = over(o, vec3(0.7, 0.78, 0.95), ground * (0.35 + 0.35 * smoothstep(0.4, 0.8, stream)));
  gl_FragColor = o;
}`;

/** Liquid metal: a chrome surface flowing slowly, drops falling on it at random and spreading rings,
 * its relief reflecting a studio — soft panels, a bright strip, a dark floor — a film of colour shimmering
 * where it bends. */
const LIQUIDMETAL = `${COMMON}
float height(vec2 p, float t) {
  vec2 w = vec2(noise(p * 0.9 + t * 0.06), noise(p * 0.9 + vec2(5.2, -t * 0.05)));
  float h = noise(p * 1.4 + w * 2.0 + t * 0.04) * 0.75 + noise(p * 3.1 + w + t * 0.05) * 0.25;
  // drops: rings spreading and dying where something fell
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float life = 4.0 + fi * 0.7;
    float k = floor((t + fi * 1.3) / life);
    float age = fract((t + fi * 1.3) / life) * life;
    vec2 at = vec2(hash(vec2(k, fi)) * 2.6, hash(vec2(k, fi + 9.0)) * 1.0) * 1.2;
    float d = length(p - at);
    h += sin((d - age * 0.35) * 38.0) * exp(-abs(d - age * 0.35) * 14.0) * exp(-age * 0.9) * 0.08;
  }
  return h;
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec2 q = p * 0.85;
  float e = 0.03;
  float h = height(q, t);
  vec3 n = normalize(vec3(height(q - vec2(e, 0.0), t) - height(q + vec2(e, 0.0), t),
                          height(q - vec2(0.0, e), t) - height(q + vec2(0.0, e), t), e * 1.3));
  vec3 rf = reflect(vec3(0.0, 0.0, -1.0), n);
  vec3 env = mix(vec3(0.06, 0.065, 0.08), vec3(0.62, 0.66, 0.75), smoothstep(-0.5, 0.7, rf.y));
  env += vec3(0.9) * smoothstep(0.7, 0.98, rf.y) * smoothstep(0.35, 0.0, abs(rf.x)); // a bright strip
  env += vec3(0.5, 0.55, 0.65) * smoothstep(0.85, 1.0, abs(rf.x)) * 0.6;            // side panels
  env += vec3(1.0) * pow(max(dot(rf, normalize(vec3(0.5, 0.6, 0.62))), 0.0), 60.0) * 1.5; // a hot spot
  vec3 film = 0.5 + 0.5 * cos(6.2831 * (h * 2.0 + vec3(0.0, 0.33, 0.67)) + t * 0.2);
  float edge = pow(1.0 - n.z, 1.4);
  vec3 col = env + film * edge * 0.5;
  float a = 0.3 + edge * 0.38;
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
  float aspect = u_res.x / u_res.y;
  float wind = sin(t * 0.5) * 0.6 + sin(t * 1.3) * 0.25;
  vec4 o = vec4(0.0);
  // the canopy's shade: patches of foliage stirring in the wind
  vec2 l = p * 13.0 + vec2(sin(t * 0.3) * 0.4, cos(t * 0.23) * 0.3);
  vec2 sway = vec2(noise(l * 0.3 + t * 0.2), noise(l * 0.3 + vec2(4.0, t * 0.17))) * 1.2;
  float leaves = noise(l * 1.7 + sway) * 0.7 + noise(l * 3.4 + sway * 2.0) * 0.3;
  float canopy = smoothstep(0.35, 0.7, fbm(p * 1.6 + vec2(t * 0.02, 0.0)));
  float dapple = smoothstep(0.58, 0.72, leaves) * canopy * smoothstep(0.2, 1.0, uv.y);
  o = over(o, vec3(0.06, 0.16, 0.05), canopy * 0.3);
  o = over(o, vec3(0.75, 0.92, 0.45), dapple * 0.45);
  // sunbeams slanting from the top left, dust glittering in them
  float bx = p.x + uv.y * 0.6;
  float shafts = smoothstep(0.55, 1.0, sin(bx * 4.0 + sin(bx * 1.7) * 1.5))
    + 0.6 * smoothstep(0.85, 1.0, sin(bx * 11.0 + 1.3));
  float beams = shafts * (0.6 + 0.4 * sin(t * 0.4 + bx * 3.0)) * (0.7 + 0.3 * noise(vec2(bx * 3.0, t * 0.3)));
  beams *= smoothstep(0.0, 0.9, uv.y);
  vec2 mg = p * 90.0 + vec2(sin(t * 0.5) * 2.0, t * 1.5);
  float motes = step(0.988, hash(floor(mg))) * smoothstep(0.35, 0.0, length(fract(mg) - 0.5)) * beams;
  o = over(o, vec3(1.0, 0.93, 0.65), beams * 0.32);
  o = over(o, vec3(1.0, 1.0, 0.85), motes);
  // the canopy's edge at the top: leaves in silhouette, swaying
  float edgeY = 0.9 + 0.05 * fbm(vec2(p.x * 3.0 + wind * 0.1, 1.0)) + 0.03 * noise(vec2(p.x * 14.0 + wind * 0.5, t * 0.3));
  float leafEdge = smoothstep(edgeY, edgeY + 0.01, uv.y + noise(vec2(p.x * 40.0, uv.y * 40.0)) * 0.04);
  o = over(o, vec3(0.02, 0.05, 0.02), leafEdge * 0.85);
  // falling leaves, tumbling
  for (int i = 0; i < 7; i++) {
    float fi = float(i);
    float life = 9.0 + hash(vec2(fi, 1.0)) * 6.0;
    float k = floor((t + fi * 2.3) / life);
    float ph = fract((t + fi * 2.3) / life);
    vec2 at = vec2(hash(vec2(k, fi)) * aspect + ph * 0.25 + sin(ph * 12.0 + fi) * 0.05, 1.02 - ph * 1.1);
    float spin = t * (1.5 + hash(vec2(fi, 4.0))) + fi;
    vec2 d = p - at;
    d = mat2(cos(spin), -sin(spin), sin(spin), cos(spin)) * d;
    float flip = 0.35 + 0.65 * abs(sin(spin * 0.7));
    float leaf = smoothstep(1.0, 0.8, length(d / vec2(0.022, 0.011 * flip)));
    leaf += smoothstep(0.0012, 0.0, abs(d.y)) * step(abs(d.x), 0.02) * 0.6; // its rib
    vec3 hue = mix(vec3(0.85, 0.55, 0.15), vec3(0.55, 0.65, 0.2), hash(vec2(k, fi + 5.0)));
    o = over(o, hue, leaf * 0.85);
  }
  // mist low over the ground
  float mist = fbm(vec2(p.x * 1.5 + t * 0.04, uv.y * 4.0 - t * 0.02)) * smoothstep(0.4, 0.0, uv.y);
  o = over(o, vec3(0.7, 0.8, 0.75), mist * 0.45);
  gl_FragColor = o;
}`;

/** A neon city at night: a synthwave sun sinking behind a skyline of towers with lit windows, a ground
 * of glowing roads running to the horizon with data streaming along them toward the viewer, flying cars
 * crossing the sky leaving trails of light, a glitch tearing the image now and then. */
const NEONCITY = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  float g = step(0.95, hash(vec2(floor(t * 3.0), 1.0)));
  float band = step(abs(uv.y - hash(vec2(floor(t * 3.0), 2.0))), 0.025);
  float x = p.x + g * band * (hash(vec2(floor(t * 3.0), 3.0)) - 0.5) * 0.15;
  float horizon = 0.5;
  vec4 o = vec4(0.0);
  if (uv.y > horizon) {
    float h = uv.y - horizon;
    // the sky: a dusk gradient, a striped sun sinking
    o = over(o, mix(vec3(0.55, 0.12, 0.45), vec3(0.06, 0.02, 0.15), smoothstep(0.0, 0.4, h)), smoothstep(0.45, 0.0, h) * 0.55);
    vec2 sun = vec2(aspect * 0.5, horizon + 0.12);
    float sd = length(vec2(x, uv.y) - sun);
    float stripes = step(0.0, sin((uv.y - horizon) * 140.0 - t * 1.5)) + step(0.14, uv.y - horizon);
    float disk = smoothstep(0.13, 0.125, sd) * min(stripes, 1.0);
    o = over(o, mix(vec3(1.0, 0.25, 0.5), vec3(1.0, 0.85, 0.3), smoothstep(-0.12, 0.12, uv.y - sun.y)), disk);
    o = over(o, vec3(1.0, 0.35, 0.6), exp(-sd * 9.0) * 0.35);
    // the skyline: towers of random heights, their windows lit
    float col = floor(x * 26.0);
    float tower = 0.03 + 0.17 * pow(hash(vec2(col, 4.0)), 1.8);
    float inTower = step(h, tower) * step(0.08, fract(x * 26.0));
    vec2 win = vec2(fract(x * 26.0 * 4.0), fract(h * 160.0));
    float lit = step(0.6, hash(vec2(col, floor(h * 160.0)) + floor(x * 104.0))) * step(0.3, win.x) * step(0.4, win.y);
    lit *= 0.6 + 0.4 * sin(t * 0.3 + hash(vec2(col, floor(h * 160.0))) * 20.0);
    o = over(o, vec3(0.03, 0.02, 0.07), inTower);
    o = over(o, mix(vec3(0.2, 0.9, 1.0), vec3(1.0, 0.4, 0.8), step(0.5, hash(vec2(col, 7.0)))), inTower * lit * 0.8);
    // flying cars: lights crossing the sky with a trail
    for (int i = 0; i < 4; i++) {
      float fi = float(i);
      float speed = 0.12 + hash(vec2(fi, 1.0)) * 0.2;
      float lane = horizon + 0.12 + fi * 0.07;
      float cx = mod(t * speed * (mod(fi, 2.0) * 2.0 - 1.0) + hash(vec2(fi, 2.0)) * 3.0, aspect + 0.6) - 0.3;
      float dx = (x - cx) * (mod(fi, 2.0) * 2.0 - 1.0);
      float car = exp(-length(vec2(dx, (uv.y - lane) * 3.0)) * 220.0);
      float trail = smoothstep(0.004, 0.0, abs(uv.y - lane)) * smoothstep(-0.2, 0.0, dx) * step(dx, 0.0);
      vec3 light = mix(vec3(1.0, 0.3, 0.3), vec3(0.4, 0.9, 1.0), mod(fi, 2.0));
      o = over(o, light, clamp(car * 2.0 + trail * 0.5, 0.0, 1.0));
    }
    gl_FragColor = o;
    return;
  }
  // the ground plane: roads to the horizon, blocks, data streaming toward the viewer
  float depth = horizon - uv.y;
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
  float fade = smoothstep(0.0, 0.16, depth);
  o = over(o, tint, road * 0.45 * fade);
  o = over(o, tint, lit * 0.3 * fade);
  o = over(o, vec3(1.0, 0.95, 0.85), clamp(pulse, 0.0, 1.0) * fade);
  o = over(o, vec3(1.0, 0.35, 0.6), exp(-depth * 18.0) * 0.35); // the horizon's glow
  o = over(o, vec3(0.4, 0.9, 1.0), g * band * 0.3);
  gl_FragColor = o;
}`;

/** Haunting: a light failing like a dying bulb, fog creeping along the floor, the dark closing in to the
 * rhythm of a heartbeat, a shadow passing — and now and then a pale figure standing in the fog (head,
 * shoulders, a frayed shroud, hollow eyes), there for a few seconds, flickering, then gone. (Pale wisps
 * are particles.) */
const HAUNTED = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  float beat = mod(t, 1.6);
  float pulse = exp(-beat * 9.0) + 0.7 * exp(-abs(beat - 0.28) * 12.0);
  vec2 c = uv - 0.5;
  float vignette = smoothstep(0.12 - pulse * 0.06, 0.72, length(c * vec2(1.25, 1.0)));
  o = over(o, vec3(0.02, 0.0, 0.01), vignette * 0.95);
  float pass = mod(t, 13.0) / 4.0;
  o = over(o, vec3(0.0), step(pass, 1.0) * smoothstep(0.35, 0.0, abs(uv.x - (pass * 1.6 - 0.3))) * 0.45);
  float k = floor(t * 12.0);
  float failing = step(0.86, hash(vec2(k, 1.0))) * step(0.5, hash(vec2(floor(t * 0.7), 2.0)));
  o = over(o, vec3(0.75, 0.8, 0.7), failing * 0.14);
  o = over(o, vec3(0.0), (1.0 - failing) * step(0.97, hash(vec2(k, 3.0))) * 0.35);
  // the figure: near or far, appearing, swaying, flickering like a bad reception, fading
  float slot = floor(t / 11.0);
  float ph = mod(t, 11.0);
  float seen = step(0.4, hash(vec2(slot, 4.0))) * smoothstep(1.5, 3.2, ph) * smoothstep(7.0, 5.2, ph);
  seen *= 0.75 + 0.25 * step(0.25, hash(vec2(floor(t * 9.0), 6.0)));
  float scale = 0.8 + 0.6 * hash(vec2(slot, 7.0));
  vec2 at = vec2(aspect * (0.12 + 0.76 * hash(vec2(slot, 5.0))), 0.06);
  vec2 f = (p - at) / scale;
  f.x -= sin(t * 0.7 + f.y * 6.0) * 0.004 * f.y * 4.0;
  float fray = (noise(vec2(f.y * 34.0, t * 0.9)) - 0.5) * 0.012 + (noise(vec2(f.x * 60.0, t)) - 0.5) * 0.02 * smoothstep(0.08, 0.0, f.y);
  float w = mix(0.062, 0.043, clamp(f.y / 0.24, 0.0, 1.0)) + fray;
  float torso = smoothstep(0.008, 0.0, abs(f.x) - w) * smoothstep(0.262, 0.248, f.y + f.x * f.x * 9.0) * step(0.0, f.y);
  float neck = smoothstep(0.004, 0.0, abs(f.x) - 0.011) * step(0.2, f.y) * step(f.y, 0.29);
  vec2 hd = (f - vec2(0.0, 0.305)) / vec2(0.022, 0.029);
  float head = smoothstep(1.0, 0.8, length(hd));
  float hollow = smoothstep(0.32, 0.18, length(vec2(abs(hd.x) - 0.38, hd.y - 0.05) * vec2(1.0, 1.4)));
  float shape = clamp(torso + neck + head, 0.0, 1.0);
  float inner = 0.55 + 0.45 * fbm(vec2(f.x * 30.0, f.y * 12.0 - t * 0.4));
  float figure = shape * inner * smoothstep(0.0, 0.1, f.y);
  float halo = exp(-length((f - vec2(0.0, 0.18)) / vec2(0.09, 0.18)) * 2.5) * 0.25;
  o = over(o, vec3(0.62, 0.7, 0.78), (figure * 0.42 + halo) * seen);
  o = over(o, vec3(0.0), hollow * head * seen * 0.6);
  // fog creeping low, slow — over the figure's feet
  float fog = fbm(vec2(p.x * 1.4 + t * 0.03, uv.y * 3.5 - t * 0.015) + fbm(p * 2.0 + t * 0.02));
  fog *= smoothstep(0.55, 0.0, uv.y);
  o = over(o, vec3(0.55, 0.6, 0.62), smoothstep(0.3, 0.8, fog) * 0.7);
  o = over(o, vec3(0.35, 0.0, 0.02), pulse * vignette * 0.18);
  gl_FragColor = o;
}`;

/** Darkness: black smoke closing in from every edge — fingers of it reaching for the middle and drawing
 * back, veins of red glowing inside, a red rim throbbing where it meets the light — and eyes in the dark:
 * almond, slit-pupilled pairs of different sizes opening at random, looking around, blinking, closing. */
const DARKNESS = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  vec2 c = uv - 0.5;
  float rr = length(c * 2.0);
  vec2 dir = normalize(c * vec2(aspect, 1.0) + 1e-5);
  float breath = 0.5 + 0.5 * sin(t * 0.23) * sin(t * 0.11 + 1.0);
  float fing = fbm(dir * 2.2 + vec2(t * 0.035, -t * 0.027));
  fing = smoothstep(0.45, 0.8, fing);
  vec2 w = vec2(fbm(p * 3.0 + t * 0.04), fbm(p * 3.0 + vec2(4.0, -t * 0.05)));
  float wisp = fbm(p * 5.0 + w * 2.0 - dir * t * 0.06);
  float limit = 1.02 - 0.12 * breath - 0.5 * fing * (0.6 + 0.4 * breath) + (wisp - 0.5) * 0.22;
  float dark = smoothstep(limit - 0.03, limit + 0.1, rr);
  float throb = 0.5 + 0.5 * sin(t * 2.4);
  float rim = exp(-abs(rr - limit) * 16.0) * (1.0 - dark * 0.7);
  o = over(o, vec3(0.5, 0.02, 0.04), rim * (0.1 + 0.16 * throb));
  vec3 smoke = vec3(0.012, 0.006, 0.008) + vec3(0.035, 0.02, 0.025) * smoothstep(0.4, 0.9, wisp);
  o = over(o, smoke, dark * 0.96);
  // veins: thin red lines running inwards along the fingers, pulsing
  float ridge = 1.0 - abs(2.0 * fbm(p * 4.0 + w * 1.6 - dir * t * 0.03) - 1.0);
  float vein = smoothstep(0.95, 0.995, ridge) * smoothstep(limit + 0.02, limit + 0.3, rr);
  o = over(o, vec3(0.7, 0.03, 0.04), vein * (0.12 + 0.22 * throb));
  // eyes: three pairs at their own rhythm, deep in the dark
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float life = 5.0 + fi * 1.7;
    float slot = floor((t + fi * 2.1) / life);
    float ph = fract((t + fi * 2.1) / life) * life;
    float shown = step(0.35, hash(vec2(slot, fi + 4.0)));
    float a = 6.2831 * hash(vec2(slot, fi + 1.0));
    float d0 = 0.84 + 0.1 * hash(vec2(slot, fi + 2.0));
    vec2 at = 0.5 + vec2(cos(a), sin(a)) * 0.5 * d0;
    at = clamp(at, vec2(0.05, 0.08), vec2(0.95, 0.92));
    float size = 0.7 + 0.9 * hash(vec2(slot, fi + 3.0));
    vec2 e = vec2((uv.x - at.x) * aspect, uv.y - at.y) / size;
    float blink = step(0.12, abs(ph - life * 0.45));
    float open = smoothstep(0.0, 0.9, ph) * smoothstep(life - 0.4, life - 1.2, ph) * blink;
    float look = sin(t * 0.9 + fi * 3.0) * 0.004;
    float gap = 0.024;
    float eyes = 0.0;
    float slit = 0.0;
    for (int j = 0; j < 2; j++) {
      vec2 d = e - vec2(j == 0 ? -gap : gap, 0.0);
      d.y *= j == 0 ? 1.0 : 1.08;
      float almond = 1.0 - length(vec2(d.x / 0.013, d.y / (0.0065 * max(open, 0.05)) + abs(d.x) * 30.0));
      float inside = smoothstep(0.0, 0.25, almond);
      eyes += inside;
      slit += inside * smoothstep(0.0028, 0.0012, abs(d.x - look));
    }
    float glow = exp(-length(e * vec2(0.6, 1.4)) * 28.0) * 0.4;
    float on = open * shown;
    o = over(o, vec3(0.8, 0.05, 0.02), glow * on);
    o = over(o, mix(vec3(1.0, 0.25, 0.05), vec3(1.0, 0.85, 0.35), clamp(eyes, 0.0, 1.0) * 0.7), clamp(eyes, 0.0, 1.0) * on);
    o = over(o, vec3(0.05, 0.0, 0.0), clamp(slit, 0.0, 1.0) * on * 0.9);
  }
  gl_FragColor = o;
}`;

/** Lost signal: a found-footage tape — grain crawling over everything, the picture wobbling, a bright
 * tear rolling down, colours split along it, the noisy band at the bottom of a worn tape, a blinking REC,
 * and now and then a cut to black. */
const LOSTSIGNAL = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  float wobble = (noise(vec2(uv.y * 6.0, t * 4.0)) - 0.5) * 0.004;
  float grain = hash(floor(gl_FragCoord.xy * 0.6) + floor(t * 24.0) * 17.0);
  o = over(o, vec3(grain), 0.2);
  float jitter = step(0.96, hash(vec2(floor(gl_FragCoord.y / 3.0), floor(t * 15.0))));
  o = over(o, vec3(0.85), jitter * 0.3);
  float roll = fract(t * 0.11);
  float near = exp(-abs(uv.y - (1.0 - roll)) * 60.0);
  float lines = step(0.5, fract(gl_FragCoord.y * 0.5)) * 0.06;
  o = over(o, vec3(0.9), near * 0.5 + lines * 0.5);
  float shift = near * (hash(vec2(floor(t * 20.0), uv.y)) - 0.5) + wobble * 30.0;
  o = over(o, vec3(1.0, 0.1, 0.2), smoothstep(0.0, 0.3, abs(shift)) * 0.22);
  o = over(o, vec3(0.1, 0.9, 1.0), smoothstep(0.0, 0.3, abs(shift * 1.3)) * 0.16);
  // the head-switching band at the bottom of a worn tape
  float bottom = step(uv.y, 0.035);
  float smear = hash(vec2(floor(gl_FragCoord.y), floor(t * 30.0))) * 0.6 + 0.2;
  o = over(o, vec3(smear), bottom * 0.55);
  // REC, blinking in the corner
  vec2 rec = vec2(0.06 * aspect, 0.93);
  float dot_ = smoothstep(0.012, 0.009, length(vec2((p.x - rec.x), uv.y - rec.y)));
  o = over(o, vec3(1.0, 0.1, 0.1), dot_ * step(0.5, fract(t * 0.8)));
  vec2 c = uv - 0.5;
  o = over(o, vec3(0.0), smoothstep(0.3, 0.72, length(c)) * 0.75);
  float cut = step(0.93, hash(vec2(floor(t * 1.5), 7.0)));
  o = over(o, vec3(0.0), cut * 0.75);
  gl_FragColor = o;
}`;

/** String lights: twisted wires sagging across the top of the page and swaying a little, hung with glass
 * bulbs — a socket, a coloured glass with its hot filament and a highlight — glowing in classic colours,
 * waves of light chasing along each string, a bulb flickering out now and then. (Snow falls as
 * particles.) */
const GARLAND = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec4 o = vec4(0.0);
  o = over(o, vec3(1.0, 0.7, 0.4), smoothstep(0.55, 1.0, uv.y) * 0.05);
  for (int s = 0; s < 3; s++) {
    float fs = float(s);
    float span = 0.55 + fs * 0.1;
    float top = 0.95 - fs * 0.13;
    float sag = 0.07 + 0.02 * fs;
    float sway = 1.0 + 0.08 * sin(t * 0.6 + fs * 1.7);
    float x = p.x / span + fs * 0.37;
    float xf = fract(x);
    float y0 = top - sag * sway * 4.0 * xf * (1.0 - xf);
    float twist = sin(p.x * 260.0) * 0.0014;
    float wire = max(smoothstep(0.0018, 0.0, abs(uv.y - y0 - twist)), smoothstep(0.0018, 0.0, abs(uv.y - y0 + twist)));
    o = over(o, vec3(0.05, 0.1, 0.06), wire * 0.85);
    float n = 9.0;
    float bi0 = floor(xf * n);
    for (int b = -1; b <= 1; b++) {
      float bi = bi0 + float(b);
      float bx = (bi + 0.5) / n;
      float id = floor(x) * 10.0 + bi + fs * 100.0;
      float by = top - sag * sway * 4.0 * bx * (1.0 - bx);
      vec2 d = vec2((xf - bx) * span, uv.y - by);
      float ang = sin(t * 1.3 + id) * 0.12;
      d = mat2(cos(ang), -sin(ang), sin(ang), cos(ang)) * d;
      float pick = floor(hash(vec2(id, 2.0)) * 5.0);
      vec3 hue = pick < 1.0 ? vec3(1.0, 0.18, 0.15) : pick < 2.0 ? vec3(0.2, 0.9, 0.35) : pick < 3.0 ? vec3(0.25, 0.5, 1.0) : pick < 4.0 ? vec3(1.0, 0.68, 0.2) : vec3(0.95, 0.3, 0.85);
      float chase = smoothstep(0.2, 1.0, sin((x - bx + bi / n) * 6.2831 * 1.5 - t * 2.2 + fs * 2.0));
      float tw = 0.75 + 0.25 * sin(t * (1.5 + hash(vec2(id, 1.0)) * 3.0) + id);
      float out_ = step(0.96, hash(vec2(id, floor(t * 0.4))));
      float lit = (0.45 + 0.55 * chase) * tw * (1.0 - out_ * 0.85);
      float socket = smoothstep(0.0012, 0.0, abs(d.x) - 0.0032) * step(-0.011, d.y) * step(d.y, 0.0);
      vec2 g = (d - vec2(0.0, -0.022)) / vec2(0.0078, 0.0135);
      g.x *= 1.0 + 0.25 * clamp(-g.y, 0.0, 1.0);
      float glass = smoothstep(1.0, 0.85, length(g));
      float core = exp(-length(g * vec2(1.4, 1.0)) * 3.0);
      float spec = smoothstep(0.32, 0.12, length(g - vec2(-0.4, 0.35)));
      float r = length(d - vec2(0.0, -0.022));
      o = over(o, hue, exp(-r * 13.0) * 0.07 * lit);
      o = over(o, hue, exp(-r * 48.0) * 0.5 * lit);
      o = over(o, vec3(0.06, 0.12, 0.07), socket);
      vec3 col = mix(hue * (0.35 + 0.65 * lit), mix(hue, vec3(1.0, 0.95, 0.85), 0.6), core * lit);
      o = over(o, col, glass * (0.75 + 0.25 * lit));
      o = over(o, vec3(1.0), spec * glass * 0.7);
    }
  }
  gl_FragColor = o;
}`;

/** Christmas night: a winter sky full of stars, a cratered moon and now and then a shooting star or a
 * sleigh with its reindeer crossing it; snowy hills with far and near fir trees, their tiers edged with
 * snow; a log cabin with a lit window spilling its light on the snow and smoke rising from the chimney,
 * and a decorated tree twinkling beside it. (Snow falls as particles.) */
const CHRISTMASNIGHT = `${COMMON}
float fir(vec2 p, float x0, float h, float w, out float snow) {
  // a fir tree: four jagged tiers, snow along their lower edges, a little trunk
  float y = p.y / h;
  float tier = fract(y * 4.0 + 0.2);
  float half_ = w * (1.0 - y) * (0.5 + 0.55 * (1.0 - tier)) * (0.92 + 0.16 * noise(vec2(p.y * 160.0, x0 * 9.0)));
  float body = step(0.0, y) * step(y, 1.0) * smoothstep(0.002, 0.0, abs(p.x - x0) - half_);
  snow = body * smoothstep(0.82, 0.95, 1.0 - tier) * step(0.06, y);
  float trunk = step(-0.02, p.y) * step(p.y, 0.0) * step(abs(p.x - x0), w * 0.12);
  return clamp(body + trunk, 0.0, 1.0);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, mix(vec3(0.03, 0.06, 0.16), vec3(0.08, 0.1, 0.25), uv.y), smoothstep(0.15, 1.0, uv.y) * 0.5);
  vec2 sg = p * 120.0;
  float sh = hash(floor(sg));
  float star = step(0.993, sh) * smoothstep(0.45, 0.0, length(fract(sg) - 0.5)) * (0.5 + 0.5 * sin(t * 2.0 + sh * 70.0));
  vec2 sg2 = p * 260.0;
  star += step(0.995, hash(floor(sg2) + 3.0)) * smoothstep(0.5, 0.0, length(fract(sg2) - 0.5)) * 0.5;
  o = over(o, vec3(1.0, 0.97, 0.88), star * smoothstep(0.3, 0.6, uv.y));
  // a shooting star, now and then
  float sslot = floor(t / 9.0);
  float sph = mod(t, 9.0);
  vec2 s0 = vec2(aspect * (0.2 + 0.6 * hash(vec2(sslot, 1.0))), 0.75 + 0.2 * hash(vec2(sslot, 2.0)));
  vec2 sdir = normalize(vec2(-0.8, -0.35));
  vec2 head = s0 + sdir * sph * 0.5;
  vec2 rel = p - head;
  float along = dot(rel, -sdir);
  float across = abs(dot(rel, vec2(-sdir.y, sdir.x)));
  float trail = smoothstep(0.0015, 0.0, across) * step(0.0, along) * exp(-along * 14.0) * step(sph, 0.7);
  o = over(o, vec3(0.9, 0.95, 1.0), trail * (1.0 - sph / 0.7) * step(0.3, hash(vec2(sslot, 3.0))));
  // the moon: a soft glow, its seas and craters
  vec2 moon = vec2(aspect * 0.78, 0.76);
  vec2 dmv = p - moon;
  float dm = length(dmv);
  o = over(o, vec3(0.95, 0.95, 0.85), exp(-dm * 9.0) * 0.32);
  float seas = fbm(dmv * 22.0 + 3.0);
  float crater = smoothstep(0.75, 0.9, noise(dmv * 120.0));
  vec3 moonc = vec3(1.0, 0.98, 0.9) * (0.9 - 0.18 * smoothstep(0.45, 0.7, seas) - 0.08 * crater) * (1.0 - 0.12 * smoothstep(0.03, 0.07, length(dmv + vec2(0.02, -0.015))));
  o = over(o, moonc, smoothstep(0.072, 0.066, dm));
  // a sleigh crossing the moon, now and then: a silhouette with its reindeer
  float pass = mod(t, 22.0) / 6.0;
  float sx = moon.x - 0.45 + pass * 0.9;
  vec2 q = p - vec2(sx, moon.y - 0.01 + sin(pass * 3.0) * 0.01);
  float sleigh = smoothstep(1.0, 0.8, length(q / vec2(0.03, 0.009)));
  sleigh += smoothstep(0.0025, 0.0, abs(q.y + 0.011)) * step(abs(q.x), 0.032);
  for (int i = 1; i < 5; i++) {
    float fi = float(i);
    vec2 r = q - vec2(0.04 + fi * 0.028, 0.012 + sin(t * 8.0 + fi) * 0.003);
    sleigh += smoothstep(1.0, 0.75, length(r / vec2(0.011, 0.0055)));
    sleigh += smoothstep(1.0, 0.7, length((r - vec2(0.011, 0.006)) / vec2(0.004, 0.0035)));
    sleigh += smoothstep(0.0012, 0.0, abs(r.x - 0.012)) * step(abs(r.y - 0.012), 0.004);
    sleigh += smoothstep(0.001, 0.0, abs(abs(r.x) - 0.006)) * step(abs(r.y + 0.008), 0.004);
  }
  o = over(o, vec3(0.02, 0.03, 0.06), clamp(sleigh, 0.0, 1.0) * step(pass, 1.0));
  // far hills with a forest of small firs, blue in the night
  float far = 0.2 + 0.04 * sin(p.x * 1.3 + 2.0) + 0.02 * noise(vec2(p.x * 4.0, 1.0));
  float fx = fract(p.x * 22.0);
  float fh = 0.025 + 0.02 * hash(vec2(floor(p.x * 22.0), 5.0));
  float farTrees = step(p.y, far + fh * (1.0 - abs(fx - 0.5) * 2.0) * step(0.3, hash(vec2(floor(p.x * 22.0), 6.0))));
  o = over(o, vec3(0.07, 0.1, 0.18), max(step(p.y, far), farTrees) * 0.95);
  o = over(o, vec3(0.45, 0.52, 0.68), step(p.y, far) * smoothstep(far - 0.03, far, p.y) * 0.5);
  float hill = 0.12 + 0.04 * sin(p.x * 2.0) + 0.02 * sin(p.x * 5.3 + 1.0);
  float ground = step(p.y, hill);
  // the near firs, leaving room for the cabin
  float cabinX = aspect * 0.64;
  float trees = 0.0;
  float snowEdge = 0.0;
  for (int i = 0; i < 9; i++) {
    float fi = float(i);
    float x0 = (fi + 0.3 * hash(vec2(fi, 1.0))) / 9.0 * aspect;
    float keep = step(0.16, abs(x0 - cabinX)) * step(0.1, abs(x0 - aspect * 0.2));
    float h = 0.16 + 0.12 * hash(vec2(fi, 2.0));
    float sn;
    float tr = fir(vec2(p.x, p.y - hill + 0.01), x0, h, 0.045 + 0.02 * hash(vec2(fi, 3.0)), sn) * keep;
    trees = max(trees, tr);
    snowEdge = max(snowEdge, sn * keep);
  }
  o = over(o, vec3(0.02, 0.06, 0.05), trees);
  o = over(o, vec3(0.7, 0.78, 0.9), snowEdge * 0.8);
  // the decorated tree: a bigger fir hung with twinkling lights and a star on top
  float tx = aspect * 0.2;
  float tbase = 0.12 + 0.04 * sin(tx * 2.0) + 0.02 * sin(tx * 5.3 + 1.0);
  float dsn;
  float big = fir(vec2(p.x, p.y - tbase + 0.01), tx, 0.3, 0.085, dsn);
  o = over(o, vec3(0.02, 0.08, 0.05), big);
  o = over(o, vec3(0.75, 0.82, 0.95), dsn * 0.75);
  vec2 lg = (p - vec2(tx, tbase)) * 70.0;
  vec2 lc = floor(lg);
  float lh = hash(lc + 11.0);
  float bulb = smoothstep(0.32, 0.1, length(fract(lg) - 0.5)) * step(0.72, lh) * big;
  float twk = 0.5 + 0.5 * sin(t * (2.0 + lh * 3.0) + lh * 40.0);
  vec3 bc = 0.55 + 0.45 * cos(6.2831 * (lh * 3.0 + vec3(0.0, 0.33, 0.67)));
  o = over(o, mix(bc, vec3(1.0, 0.9, 0.6), 0.3), bulb * (0.4 + 0.6 * twk));
  vec2 st = p - vec2(tx, tbase + 0.3);
  float sa = atan(st.y, st.x);
  float starShape = smoothstep(0.012, 0.009, length(st) / (0.6 + 0.4 * cos(sa * 5.0 - 1.57)));
  o = over(o, vec3(1.0, 0.85, 0.35), exp(-length(st) * 40.0) * (0.5 + 0.2 * sin(t * 3.0)));
  o = over(o, vec3(1.0, 0.92, 0.55), starShape);
  // snow ground: blue shadows in the drifts
  float drift = fbm(vec2(p.x * 3.0, p.y * 12.0));
  o = over(o, mix(vec3(0.55, 0.62, 0.8), vec3(0.82, 0.88, 0.98), drift), ground * 0.92);
  // the cabin: log walls, a snowed roof, a warm window, a chimney smoking
  float cb = 0.12 + 0.04 * sin(cabinX * 2.0) + 0.02 * sin(cabinX * 5.3 + 1.0) - 0.01;
  vec2 cq = p - vec2(cabinX, cb);
  float walls = step(abs(cq.x), 0.08) * step(0.0, cq.y) * step(cq.y, 0.075);
  float logs = 0.75 + 0.25 * smoothstep(0.2, 0.5, abs(fract(cq.y * 110.0) - 0.5));
  float roof = step(cq.y, 0.075 + 0.06 - abs(cq.x) * 0.62) * step(0.07, cq.y) * step(abs(cq.x), 0.1);
  float roofSnow = roof * step(0.075 + 0.06 - abs(cq.x) * 0.62 - 0.012 - 0.004 * noise(vec2(cq.x * 90.0, 2.0)), cq.y);
  vec2 chim = cq - vec2(0.045, 0.12);
  float chimney = step(abs(chim.x), 0.008) * step(-0.04, chim.y) * step(chim.y, 0.0);
  o = over(o, vec3(0.13, 0.07, 0.04) * logs, walls);
  o = over(o, vec3(0.06, 0.035, 0.03), max(roof, chimney));
  o = over(o, vec3(0.88, 0.92, 1.0), roofSnow);
  float flick = 0.85 + 0.15 * noise(vec2(t * 5.0, 3.0));
  vec2 win = cq - vec2(-0.03, 0.038);
  float pane = step(abs(win.x), 0.017) * step(abs(win.y), 0.014);
  float mullion = step(abs(win.x), 0.0015) + step(abs(win.y), 0.0015);
  o = over(o, vec3(1.0, 0.72, 0.32) * flick, pane * (1.0 - clamp(mullion, 0.0, 1.0)));
  vec2 door = cq - vec2(0.035, 0.022);
  o = over(o, vec3(0.07, 0.04, 0.02), step(abs(door.x), 0.013) * step(abs(door.y), 0.022));
  o = over(o, vec3(1.0, 0.7, 0.35), exp(-length(win * vec2(1.0, 1.6)) * 30.0) * 0.35 * flick * (1.0 - pane));
  vec2 spill = (p - vec2(cabinX - 0.03, cb - 0.02)) / vec2(0.09, 0.025);
  o = over(o, vec3(1.0, 0.75, 0.4), exp(-dot(spill, spill)) * 0.35 * flick * ground);
  vec2 sm = chim - vec2(0.0, 0.005);
  float rise = max(sm.y, 0.0);
  float plume = fbm(vec2(sm.x * 30.0 - rise * 18.0, rise * 9.0 - t * 0.5));
  float width = 0.008 + rise * 0.35;
  float smoke = smoothstep(width, 0.0, abs(sm.x - rise * rise * 2.5 - (plume - 0.5) * 0.03)) * step(0.0, sm.y) * smoothstep(0.22, 0.0, rise);
  o = over(o, vec3(0.62, 0.64, 0.72), smoke * smoothstep(0.25, 0.65, plume) * 0.7);
  // snow on the hills sparkling
  float sparkle = step(0.997, hash(floor(p * 200.0) + floor(t * 3.0))) * ground;
  o = over(o, vec3(1.0), sparkle);
  gl_FragColor = o;
}`;

/** By the fire: a hearth at the bottom of the page — logs crossed on the bed of embers, their cracks
 * glowing, fine flames licking up from them with a blue foot, a warm light flickering over the whole
 * page — and a thin frost of branching ice crystals at the corners of the window. (Embers crackle as
 * particles.) */
const HEARTH = `${COMMON}
float capsule(vec2 p, vec2 a, vec2 b, float r) {
  vec2 pa = p - a;
  vec2 ba = b - a;
  float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
  return length(pa - ba * h) - r;
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  float cx = aspect * 0.5;
  float flicker = 0.8 + 0.12 * sin(t * 1.7) + 0.08 * (noise(vec2(t * 6.0, 0.0)) - 0.5) * 2.0;
  // the warm light of the fire over the whole room
  o = over(o, vec3(1.0, 0.5, 0.15), (0.04 + 0.05 * smoothstep(0.8, 0.0, uv.y)) * flicker);
  float hx = (p.x - cx) / (aspect * 0.42);
  float env = exp(-hx * hx * 1.6);
  o = over(o, vec3(0.95, 0.4, 0.08), smoothstep(0.55, 0.0, uv.y) * (0.12 + 0.2 * env) * flicker);
  // the flames: rising tongues, a blue foot, a white-hot heart
  vec2 q = vec2(p.x * 5.0, p.y * 3.2 - t * 1.9);
  float n = fbm(q + vec2(fbm(q * 1.6 - vec2(0.0, t * 0.9)), 0.0) * 1.3);
  float tongues = 0.5 + 0.5 * sin(p.x * 22.0 + noise(vec2(p.x * 3.0, t)) * 6.0);
  float env2 = env * env;
  float height = (0.025 + 0.27 * env2) * (0.7 + 0.5 * tongues) * (0.8 + 0.25 * noise(vec2(p.x * 2.0, t * 1.3)));
  float f = clamp((1.0 - (uv.y - 0.02) / height) * (0.6 + 0.5 * env2) + (n - 0.55) * 1.6, 0.0, 1.0);
  f *= smoothstep(0.0, 0.03, uv.y + 0.01);
  vec3 fc = mix(vec3(0.7, 0.12, 0.02), vec3(1.0, 0.5, 0.08), smoothstep(0.1, 0.5, f));
  fc = mix(fc, vec3(1.0, 0.85, 0.45), smoothstep(0.55, 0.85, f));
  fc = mix(fc, vec3(1.0, 0.97, 0.85), smoothstep(0.9, 1.0, f) * env2);
  float blue = smoothstep(0.07, 0.035, uv.y) * smoothstep(0.02, 0.04, uv.y) * smoothstep(0.3, 0.6, f) * env;
  fc = mix(fc, vec3(0.3, 0.45, 1.0), blue * 0.5);
  o = over(o, fc, smoothstep(0.05, 0.45, f) * (0.55 + 0.37 * env));
  // the logs, crossed in the middle, charred, glowing in their cracks
  float logs = 1e3;
  logs = min(logs, capsule(p, vec2(cx - 0.32, 0.025), vec2(cx + 0.08, 0.06), 0.024));
  logs = min(logs, capsule(p, vec2(cx + 0.34, 0.022), vec2(cx - 0.06, 0.065), 0.026));
  logs = min(logs, capsule(p, vec2(cx - 0.12, 0.012), vec2(cx + 0.16, 0.014), 0.02));
  float wood = smoothstep(0.002, -0.002, logs);
  float crack = 1.0 - abs(2.0 * fbm(p * vec2(30.0, 60.0) + vec2(0.0, t * 0.05)) - 1.0);
  float ember = smoothstep(0.93, 0.99, crack) * (0.5 + 0.5 * sin(t * 2.0 + p.x * 30.0));
  float bark = 0.7 + 0.3 * noise(p * vec2(60.0, 200.0));
  float rimLight = smoothstep(-0.012, 0.0, logs) * step(0.03, p.y);
  vec3 woodc = mix(vec3(0.09, 0.045, 0.025) * bark, vec3(1.0, 0.45, 0.08), ember);
  woodc += vec3(0.5, 0.18, 0.03) * rimLight * flicker;
  o = over(o, woodc, wood);
  // the bed of embers along the bottom, breathing
  float bed = smoothstep(0.03, 0.0, uv.y) * smoothstep(0.35, 0.75, noise(vec2(p.x * 40.0, t * 0.8))) * (0.25 + 0.75 * env);
  o = over(o, vec3(1.0, 0.35, 0.05), bed * 0.8);
  // frost at the corners: fine branching crystals, a misted pane
  vec2 cc = min(uv, 1.0 - uv) * vec2(aspect, 1.0);
  float corner = length(cc);
  float grow = 0.18 + 0.03 * sin(t * 0.15);
  float reach = smoothstep(grow, grow * 0.3, corner + (fbm(p * 6.0) - 0.5) * 0.08);
  o = over(o, vec3(0.75, 0.85, 0.95), reach * 0.1);
  float branch = 1.0 - abs(2.0 * fbm(p * 18.0 + fbm(p * 7.0) * 1.5) - 1.0);
  float twig = 1.0 - abs(2.0 * fbm(p * 48.0 + 5.0) - 1.0);
  float lines = smoothstep(0.97, 0.997, branch) + 0.4 * smoothstep(0.975, 0.998, twig);
  o = over(o, vec3(0.9, 0.96, 1.0), lines * reach * 0.45 * (1.0 - smoothstep(0.4, 0.0, uv.y) * 0.6));
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
