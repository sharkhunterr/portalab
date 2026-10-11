import { COMMON } from "./shaders";

/**
 * #68: the warm and cheerful premium ambiences — golden hour, rain on the window seen from inside, a
 * summer field, soap bubbles, sky lanterns over a lake, an autumn lane — and three scenes in detailed,
 * animated pixel art (a campfire, a sunset beach, hot-air balloons). Same rules as the others: premultiplied
 * colour over a transparent page, GLSL ES 1.0.
 */

/** Pixel art: the scene is drawn on a grid of about 180 rows whatever the screen (each art pixel a block of
 * screen pixels), its gradients shaded with an ordered (Bayer) dither like the consoles of old. */
const PIXEL = `${COMMON}
float bayer2(vec2 a) {
  a = floor(a);
  return fract(dot(a, vec2(0.5, a.y * 0.75)));
}
float bayer4(vec2 a) {
  return bayer2(0.5 * a) * 0.25 + bayer2(a);
}
// a two-colour gradient the old way: v from 0 to 1 picks a or b, the dither mixing them in between
vec3 dither(vec3 a, vec3 b, float v, vec2 px) {
  return step(bayer4(px), clamp(v, 0.0, 1.0)) > 0.5 ? b : a;
}
`;

/** Golden hour: the low sun at the corner of the page, its rays sweeping across, light dappled through
 * swaying leaves, lens flares, soft bokeh rising slowly. (Golden dust drifts as particles.) */
const GOLDENHOUR = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  vec2 sun = vec2(aspect * 0.9, 0.98);
  vec2 d = p - sun;
  float r = length(d);
  o = over(o, vec3(1.0, 0.6, 0.25), 0.05 + 0.24 * exp(-r * 1.4));
  float a = atan(d.x, -d.y);
  float rays = pow(noise(vec2(a * 18.0 + t * 0.04, t * 0.07)), 2.5) * 0.7 + pow(noise(vec2(a * 41.0 - t * 0.03, 3.0 + t * 0.05)), 3.0) * 0.5;
  o = over(o, vec3(1.0, 0.78, 0.45), rays * exp(-r * 0.9) * 0.3);
  // light through leaves swaying in the breeze
  vec2 sway = vec2(sin(t * 0.4), cos(t * 0.33)) * 0.03;
  float leaves = fbm(p * 3.2 + sway + vec2(t * 0.01, 0.0));
  float spots = smoothstep(0.58, 0.66, leaves) * smoothstep(1.6, 0.3, r);
  o = over(o, vec3(1.0, 0.82, 0.5), spots * 0.12);
  o = over(o, vec3(1.0, 0.95, 0.8), exp(-r * 9.0) * 0.8);
  // lens flares on the line from the sun through the middle
  vec2 axis = vec2(aspect * 0.5, 0.5) - sun;
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    vec2 g = sun + axis * (0.45 + fi * 0.38);
    float rad = 0.02 + 0.03 * hash(vec2(fi, 1.0)) + fi * 0.006;
    float dg = length(p - g);
    vec3 tint = fi == 1.0 ? vec3(0.5, 0.9, 0.7) : fi == 3.0 ? vec3(0.7, 0.6, 1.0) : vec3(1.0, 0.7, 0.4);
    float disc = smoothstep(rad, rad * 0.85, dg) * 0.05 + smoothstep(0.004, 0.0, abs(dg - rad)) * 0.06;
    o = over(o, tint, disc * (0.8 + 0.2 * sin(t * 0.5 + fi)));
  }
  // bokeh, rising slowly
  for (int i = 0; i < 12; i++) {
    float fi = float(i);
    float sp = 0.01 + 0.02 * hash(vec2(fi, 3.0));
    vec2 b = vec2(aspect * hash(vec2(fi, 4.0)) + sin(t * 0.2 + fi) * 0.05, fract(hash(vec2(fi, 5.0)) + t * sp) * 1.3 - 0.15);
    float rad = 0.025 + 0.05 * hash(vec2(fi, 6.0));
    float db = length(p - b);
    float shape = smoothstep(rad, rad * 0.8, db);
    float edge = smoothstep(rad * 0.7, rad, db) * shape;
    vec3 col = mix(vec3(1.0, 0.7, 0.35), vec3(1.0, 0.9, 0.6), hash(vec2(fi, 7.0)));
    o = over(o, col, (shape * 0.05 + edge * 0.07) * (0.6 + 0.4 * sin(t * 0.7 + fi * 2.0)));
  }
  gl_FragColor = o;
}`;

/** Rain on the window, from inside: the town's lights blurred behind the glass, drops clinging and
 * sliding down in jerks, leaving trails of droplets, each drop showing the lights upside down; mist on the
 * pane and the warm lamp of the room. */
const WINDOWRAIN = `${COMMON}
vec4 lights(vec2 p, float t, float aspect) {
  vec4 o = vec4(0.0);
  for (int i = 0; i < 24; i++) {
    float fi = float(i);
    vec2 c = vec2(hash(vec2(fi, 1.0)) * aspect, 0.03 + 0.75 * hash(vec2(fi, 2.0)));
    c.x += sin(t * 0.05 + fi) * 0.01;
    float rad = 0.05 + 0.09 * hash(vec2(fi, 3.0));
    float d = length(p - c);
    float pick = hash(vec2(fi, 4.0));
    vec3 col = pick < 0.5 ? vec3(1.0, 0.72, 0.35) : pick < 0.7 ? vec3(1.0, 0.45, 0.3) : pick < 0.85 ? vec3(0.45, 0.7, 1.0) : vec3(1.0, 0.9, 0.7);
    float on = 0.7 + 0.3 * sin(t * (0.3 + pick) + fi);
    o = over(o, col, smoothstep(rad, rad * 0.55, d) * 0.26 * on);
  }
  return o;
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = lights(p, t, aspect);
  o = over(o, vec3(1.0, 0.7, 0.4), exp(-length((uv - vec2(0.0, 0.0)) * vec2(aspect, 1.0)) * 2.5) * 0.18);
  float mist = fbm(p * 3.0 + vec2(0.0, t * 0.01));
  o = over(o, vec3(0.62, 0.66, 0.75), (0.03 + 0.1 * smoothstep(0.45, 0.0, uv.y)) * smoothstep(0.3, 0.8, mist));
  // sliding drops in two depths: each column of cells falls at its own pace, in jerks
  for (int l = 0; l < 2; l++) {
    float s = l == 0 ? 7.0 : 12.0;
    vec2 g = p * vec2(s, s * 0.45);
    float col = floor(g.x);
    float hc = hash(vec2(col, s));
    float jerk = t * (0.35 + 0.5 * hc) + 0.15 * sin(t * (2.0 + hc * 3.0) + col);
    g.y += jerk + hc * 7.0;
    vec2 id = floor(g);
    vec2 f = fract(g) - vec2(0.5, 0.3);
    float h = hash(id + s);
    float present = step(0.62, h);
    float dx = (h - 0.5) * 0.5 + sin(g.y * 3.0 + h * 9.0) * 0.06;
    vec2 dp = vec2((f.x - dx) / s, f.y / (s * 0.45));
    float r0 = (0.11 + 0.08 * hash(id + 3.0)) / s;
    vec2 n = dp / r0;
    float body = smoothstep(1.0, 0.85, length(n * vec2(1.0, 0.85))) * present;
    float trail = smoothstep(r0 * 0.35, 0.0, abs(dp.x)) * step(0.0, dp.y) * smoothstep(0.3 / s, 0.0, dp.y) * present;
    vec4 seen = lights(p - n * 0.06 * vec2(1.0, -1.0) * 3.0, t, aspect);
    o = over(o, vec3(0.8, 0.85, 0.95), body * 0.12 + trail * 0.05);
    o = over(o, seen.rgb / max(seen.a, 0.01), body * clamp(seen.a * 3.0, 0.0, 0.8));
    o = over(o, vec3(0.05, 0.06, 0.1), body * smoothstep(0.55, 1.0, length(n)) * 0.35 * step(n.y, 0.2));
    o = over(o, vec3(1.0), body * smoothstep(0.3, 0.1, length(n - vec2(-0.35, 0.4))) * 0.8);
  }
  // still droplets scattered on the pane, appearing and drying
  vec2 sg = p * 55.0;
  vec2 sid = floor(sg);
  float sh = hash(sid + 9.0);
  float alive = sin(t * (0.1 + sh * 0.2) + sh * 40.0);
  vec2 sp = fract(sg) - 0.5 - (vec2(hash(sid + 1.0), hash(sid + 2.0)) - 0.5) * 0.5;
  float droplet = smoothstep(0.18, 0.1, length(sp)) * step(0.88, sh) * smoothstep(0.0, 0.3, alive);
  o = over(o, vec3(0.85, 0.88, 0.95), droplet * 0.3);
  o = over(o, vec3(1.0), droplet * smoothstep(0.08, 0.02, length(sp - vec2(-0.04, 0.05))) * 0.6);
  gl_FragColor = o;
}`;

/** A summer field: a blue sky with fluffy clouds drifting, a smiling sun, rolling hills in patchwork,
 * little trees, flowers and grass swaying in the breeze at the front. (Butterflies flutter as particles.) */
const SUMMERFIELD = `${COMMON}
float hillAt(float x, float base, float a, float f, float ph) {
  return base + a * sin(x * f + ph) + a * 0.5 * sin(x * f * 2.3 + ph * 1.7);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, mix(vec3(0.55, 0.78, 1.0), vec3(0.25, 0.52, 0.95), uv.y), 0.3 + smoothstep(0.25, 1.0, uv.y) * 0.3);
  vec2 sun = vec2(aspect * 0.12, 0.86);
  float rs = length(p - sun);
  float ang = atan(p.y - sun.y, p.x - sun.x);
  o = over(o, vec3(1.0, 0.9, 0.5), exp(-rs * 4.0) * 0.35);
  o = over(o, vec3(1.0, 0.92, 0.55), smoothstep(0.004, 0.0, abs(rs - 0.075 - 0.012 * sin(ang * 12.0 + t))) * step(0.07, rs) * 0.5);
  o = over(o, vec3(1.0, 0.93, 0.6), smoothstep(0.052, 0.048, rs));
  // fluffy clouds: lit tops, a soft grey-blue underside
  for (int l = 0; l < 2; l++) {
    float fl = float(l);
    vec2 cq = vec2(p.x * (1.4 + fl * 0.8) - t * (0.015 + fl * 0.01) + fl * 5.0, uv.y * (3.0 + fl));
    float c = fbm(cq) + 0.5 * fbm(cq * 2.0 + 3.0) - 0.15;
    float band = smoothstep(0.5, 0.75, uv.y) * smoothstep(1.0, 0.85, uv.y);
    float cloud = smoothstep(0.62, 0.72, c * band + 0.25 * band);
    float under = smoothstep(0.0, 0.1, fbm(cq + vec2(0.0, 0.15)) - fbm(cq));
    o = over(o, mix(vec3(1.0), vec3(0.82, 0.88, 0.97), under * 0.8), cloud * (0.92 - fl * 0.2));
  }
  // the far hills with their little trees, the middle ones in patchwork fields, the near meadow
  float h1 = hillAt(p.x, 0.27, 0.025, 2.1, 1.0);
  float tree = step(0.6, hash(vec2(floor(p.x * 60.0), 1.0))) * smoothstep(0.006, 0.004, length(vec2((fract(p.x * 60.0) - 0.5) / 60.0, p.y - h1 - 0.006)));
  o = over(o, mix(vec3(0.5, 0.72, 0.55), vec3(0.4, 0.66, 0.4), smoothstep(h1, h1 - 0.06, p.y)) * (0.92 + 0.12 * fbm(p * 12.0)), max(step(p.y, h1), tree * 0.9) * 0.95);
  o = over(o, vec3(0.25, 0.45, 0.28), tree);
  float h2 = hillAt(p.x, 0.19, 0.03, 1.6, 2.5);
  vec2 fq = mat2(0.9, -0.44, 0.44, 0.9) * p * vec2(9.0, 22.0);
  float field = hash(floor(fq));
  vec3 fieldc = field < 0.3 ? vec3(0.85, 0.78, 0.35) : field < 0.6 ? vec3(0.45, 0.72, 0.32) : field < 0.8 ? vec3(0.62, 0.8, 0.38) : vec3(0.7, 0.55, 0.35);
  float hedge = smoothstep(0.06, 0.0, min(fract(fq.x), fract(fq.y)));
  fieldc *= 0.9 + 0.2 * noise(fq * 4.0 + p * 80.0);
  o = over(o, mix(fieldc, vec3(0.2, 0.4, 0.22), hedge * 0.8), step(p.y, h2));
  float h3 = hillAt(p.x, 0.1, 0.025, 1.1, 4.0);
  float meadow = step(p.y, h3);
  o = over(o, mix(vec3(0.3, 0.6, 0.25), vec3(0.42, 0.72, 0.3), fbm(p * 8.0)), meadow);
  // flowers on the meadow, nodding
  vec2 fg = p * vec2(70.0, 70.0);
  vec2 fid = floor(fg);
  float fh = hash(fid + 5.0);
  vec2 fp = fract(fg) - 0.5 - vec2(sin(t * 1.5 + fid.x * 0.7) * 0.12, 0.0);
  float bloom = smoothstep(0.24, 0.16, length(fp)) * step(0.82, fh) * step(p.y, h3 - 0.01);
  vec3 petal = fh < 0.87 ? vec3(1.0, 0.3, 0.3) : fh < 0.91 ? vec3(1.0, 0.85, 0.2) : fh < 0.95 ? vec3(1.0, 1.0, 1.0) : vec3(0.75, 0.45, 1.0);
  o = over(o, petal, bloom);
  o = over(o, vec3(1.0, 0.85, 0.3), smoothstep(0.08, 0.04, length(fp)) * bloom);
  // grass blades swaying in the breeze, two rows
  for (int l = 0; l < 2; l++) {
    float fl = float(l);
    float k = 150.0 + fl * 70.0;
    float bx = floor(p.x * k + fl * 0.5);
    float bh = (0.035 + 0.05 * hash(vec2(bx, fl + 2.0))) * (1.0 - fl * 0.3);
    float yy = clamp(p.y / bh, 0.0, 1.0);
    float lean = (sin(t * 1.3 + bx * 0.15 + fl) * 0.8 + 0.4 * sin(t * 2.7 + bx * 0.4)) * yy * yy * 1.5;
    float fx = fract(p.x * k + fl * 0.5) - 0.5 - lean;
    float blade = step(abs(fx), 0.35 * (1.0 - yy)) * step(p.y, bh);
    o = over(o, mix(vec3(0.2, 0.45, 0.15), vec3(0.45, 0.75, 0.3), yy) * (1.0 - fl * 0.15), blade);
  }
  gl_FragColor = o;
}`;

/** Soap bubbles: iridescent bubbles rising and wobbling, their thin film swirling with colours, a window
 * reflected in each, and now and then one bursting into a ring of droplets. */
const SOAPBUBBLES = `${COMMON}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, vec3(1.0, 0.75, 0.85), smoothstep(0.7, 0.0, length(uv - vec2(0.0, 1.0))) * 0.06);
  o = over(o, vec3(0.6, 0.85, 1.0), smoothstep(0.7, 0.0, length(uv - vec2(1.0, 0.0))) * 0.06);
  for (int i = 0; i < 14; i++) {
    float fi = float(i);
    float life = 9.0 + 6.0 * hash(vec2(fi, 1.0));
    float tt = t + hash(vec2(fi, 2.0)) * life;
    float slot = floor(tt / life);
    float ph = fract(tt / life);
    float rad = 0.03 + 0.07 * hash(vec2(slot, fi + 3.0));
    float popAt = 0.55 + 0.45 * hash(vec2(slot, fi + 4.0));
    vec2 c = vec2(aspect * hash(vec2(slot, fi + 5.0)) + sin(ph * 6.0 + fi) * 0.04 + ph * 0.15 * (hash(vec2(slot, fi + 6.0)) - 0.5),
                  -0.12 + ph * 1.25);
    vec2 d = p - c;
    if (ph < popAt) {
      float ang = atan(d.y, d.x);
      float wob = 1.0 + 0.014 * sin(ang * 3.0 + t * 2.0 + fi) + 0.007 * sin(ang * 5.0 - t * 3.0);
      float dist = length(d) / (rad * wob);
      float film = fbm(d / rad * 1.4 + vec2(t * 0.25, fi * 3.0)) + dist * 0.4 + t * 0.05;
      vec3 irid = 0.5 + 0.5 * cos(6.2831 * (film * 1.6 + vec3(0.0, 0.33, 0.67)));
      float body = smoothstep(1.0, 0.96, dist);
      float rim = smoothstep(0.8, 1.0, dist) * body;
      o = over(o, mix(irid, vec3(1.0), 0.25), body * 0.05 + rim * 0.55);
      vec2 l = d / rad;
      float win = smoothstep(0.2, 0.1, length((l - vec2(-0.38, 0.42)) * vec2(1.0, 1.6)));
      float win2 = smoothstep(0.1, 0.04, length(l - vec2(0.42, -0.45)));
      o = over(o, vec3(1.0), (win * 0.75 + win2 * 0.4) * body);
    } else {
      float k = (ph - popAt) / 0.04;
      float fade = 1.0 - clamp(k, 0.0, 1.0);
      float ring = smoothstep(0.003, 0.0, abs(length(d) - rad * (1.0 + k * 0.6)));
      float ang = atan(d.y, d.x);
      float bits = step(0.7, fract(ang * 9.0 / 6.2831 + fi)) * smoothstep(0.006, 0.0, abs(length(d) - rad * (1.0 + k * 1.4)));
      o = over(o, vec3(0.9, 0.95, 1.0), (ring * 0.5 + bits * 0.8) * fade);
    }
  }
  gl_FragColor = o;
}`;

/** Sky lanterns: a dusk sky over a calm lake, paper lanterns rising slowly — near and far — swaying,
 * their flames breathing, each mirrored in the rippling water. */
const SKYLANTERNS = `${COMMON}
vec4 lantern(vec2 p, vec2 c, float size, float flick, vec4 o, float alpha) {
  vec2 q = (p - c) / size;
  float half_ = 0.55 + 0.16 * q.y;
  float body = smoothstep(0.08, 0.0, abs(q.x) - half_) * smoothstep(0.08, 0.0, abs(q.y) - 1.0);
  vec3 col = mix(vec3(1.0, 0.86, 0.5), vec3(0.95, 0.42, 0.15), (q.y + 1.0) * 0.5) * flick;
  float glow = exp(-length(q * vec2(1.0, 0.8)) * 1.1) * 0.35;
  float flame = smoothstep(0.35, 0.0, length((q - vec2(0.0, -0.75)) * vec2(1.4, 0.9)));
  o = over(o, vec3(1.0, 0.6, 0.25), glow * alpha * flick);
  o = over(o, col, body * alpha * 0.95);
  o = over(o, vec3(0.6, 0.25, 0.1), body * smoothstep(0.75, 1.0, q.y) * alpha * 0.6);
  o = over(o, vec3(1.0, 0.97, 0.8), flame * alpha);
  return o;
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  float horizon = 0.22;
  vec3 sky = mix(vec3(1.0, 0.55, 0.3), vec3(0.4, 0.22, 0.5), smoothstep(horizon, 0.6, uv.y));
  sky = mix(sky, vec3(0.07, 0.07, 0.2), smoothstep(0.55, 1.0, uv.y));
  o = over(o, sky, step(horizon, uv.y) * 0.4);
  vec2 sg = p * 110.0;
  float st = step(0.995, hash(floor(sg))) * smoothstep(0.4, 0.0, length(fract(sg) - 0.5)) * (0.5 + 0.5 * sin(t * 2.0 + hash(floor(sg)) * 50.0));
  o = over(o, vec3(1.0, 0.95, 0.85), st * smoothstep(0.6, 0.9, uv.y));
  float shore = horizon + 0.02 + 0.025 * noise(vec2(p.x * 3.0, 1.0)) + 0.015 * sin(p.x * 1.7);
  o = over(o, vec3(0.12, 0.08, 0.17), step(horizon, uv.y) * step(uv.y, shore) * 0.95);
  float depth = (horizon - uv.y) / horizon;
  vec3 water = mix(vec3(0.55, 0.3, 0.35), vec3(0.06, 0.06, 0.16), depth);
  float wave = noise(vec2(p.x * 4.0, uv.y * 140.0 / (0.3 + depth) + t * 0.6));
  o = over(o, water + vec3(0.2, 0.12, 0.08) * smoothstep(0.6, 0.9, wave) * (1.0 - depth), step(uv.y, horizon) * 0.85);
  for (int i = 0; i < 22; i++) {
    float fi = float(i);
    float near = hash(vec2(fi, 1.0));
    near = near * near;
    float size = 0.006 + 0.022 * near;
    float speed = 0.012 + 0.03 * near;
    float ph = fract(hash(vec2(fi, 2.0)) + t * speed);
    vec2 c = vec2(aspect * hash(vec2(fi, 3.0)) + sin(t * 0.3 + fi) * 0.02 + ph * 0.12 * (hash(vec2(fi, 4.0)) - 0.3), horizon + 0.03 + ph * 0.95);
    float flick = 0.85 + 0.15 * noise(vec2(t * 4.0, fi));
    float alpha = smoothstep(0.0, 0.08, ph) * smoothstep(1.0, 0.75, ph) * (0.55 + 0.45 * near);
    o = lantern(p, c, size, flick, o, alpha * step(horizon, uv.y));
    // its reflection in the lake, broken by the ripples
    vec2 rp = vec2(p.x + sin(uv.y * 260.0 + t * 2.0) * 0.004, 2.0 * horizon - p.y);
    o = lantern(rp, c, size, flick, o, alpha * 0.35 * step(uv.y, horizon) * smoothstep(0.0, 0.3, horizon - (c.y - horizon)));
  }
  gl_FragColor = o;
}`;

/** An autumn lane: warm afternoon haze, a branch heavy with red and gold leaves at the corner, maple leaves
 * falling — swinging like pendulums, flipping, veined — and a bed of fallen leaves along the bottom.
 * (Golden dust drifts as particles.) */
const AUTUMNLANE = `${COMMON}
vec3 leafColor(float h) {
  return h < 0.25 ? vec3(0.85, 0.25, 0.08) : h < 0.5 ? vec3(0.95, 0.55, 0.1) : h < 0.75 ? vec3(0.95, 0.75, 0.2) : vec3(0.6, 0.18, 0.08);
}
float maple(vec2 q, out float vein) {
  float r = length(q);
  float a = atan(q.x, q.y);
  float R = 0.55 + 0.25 * cos(5.0 * a) + 0.05 * abs(sin(a * 20.0));
  float leaf = smoothstep(0.03, 0.0, r - R * 0.9);
  vein = leaf * smoothstep(0.05, 0.0, abs(fract(a * 5.0 / 6.2831 + 0.5) - 0.5) * r * 2.0) * step(0.08, r);
  float stem = smoothstep(0.04, 0.0, abs(q.x)) * step(q.y, -0.2) * step(-0.85, q.y);
  return clamp(leaf + stem, 0.0, 1.0);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, vec3(1.0, 0.65, 0.3), 0.04 + 0.12 * smoothstep(1.2, 0.0, length(uv - vec2(0.0, 1.0))));
  // the branch at the top-right corner, its leaves stirring
  vec2 bq = p - vec2(aspect, 1.0);
  float branch = smoothstep(0.003, 0.0, abs(bq.y + 0.06 + bq.x * 0.25 + 0.04 * sin(bq.x * 8.0)) - 0.003 * (1.0 - bq.x * 4.0)) * step(-0.55, bq.x);
  float crown = fbm(p * 9.0 + vec2(sin(t * 0.6) * 0.15, 0.0));
  float canopy = smoothstep(0.3, 0.0, length(bq * vec2(0.8, 1.6)) - 0.12 - crown * 0.18);
  float clump = smoothstep(0.5, 0.56, crown) * canopy;
  o = over(o, vec3(0.2, 0.1, 0.05), branch);
  vec3 crownc = mix(vec3(0.8, 0.22, 0.07), vec3(0.98, 0.7, 0.18), smoothstep(0.3, 0.7, noise(p * 14.0)));
  crownc *= 0.7 + 0.45 * smoothstep(0.5, 0.75, crown);
  o = over(o, crownc, clump * 0.95);
  // falling leaves
  for (int i = 0; i < 14; i++) {
    float fi = float(i);
    float life = 8.0 + 5.0 * hash(vec2(fi, 1.0));
    float tt = t + hash(vec2(fi, 2.0)) * life;
    float slot = floor(tt / life);
    float ph = fract(tt / life);
    float size = 0.022 + 0.022 * hash(vec2(slot, fi + 3.0));
    float swing = sin(ph * 12.0 + fi);
    vec2 c = vec2(aspect * (0.1 + 0.95 * hash(vec2(slot, fi + 4.0))) - ph * 0.25 + swing * 0.06, 1.08 - ph * 1.2 + abs(swing) * 0.015);
    float rot = swing * 0.9 + fi;
    vec2 q = (p - c) / size;
    q = mat2(cos(rot), -sin(rot), sin(rot), cos(rot)) * q;
    q.x /= max(0.4, abs(cos(t * (0.6 + 0.6 * hash(vec2(fi, 5.0))) + fi)));
    float vein;
    float m = maple(q, vein);
    vec3 col = leafColor(hash(vec2(slot, fi + 6.0)));
    col *= 0.85 + 0.25 * smoothstep(-0.6, 0.6, q.x + q.y);
    o = over(o, col, m * 0.95);
    o = over(o, col * 0.55, vein * 0.6);
  }
  // the bed of fallen leaves along the bottom
  float top = 0.05 + 0.02 * noise(vec2(p.x * 6.0, 1.0)) + 0.01 * sin(p.x * 3.0);
  float bed = smoothstep(0.005, 0.0, p.y - top);
  o = over(o, vec3(0.22, 0.1, 0.05), bed * 0.95);
  for (int l = 0; l < 3; l++) {
    float fl = float(l);
    vec2 lg = p * 42.0 + vec2(fl * 0.37, fl * 0.61);
    vec2 lid = floor(lg);
    float a = hash(lid + fl) * 6.2831;
    vec2 lq = mat2(cos(a), -sin(a), sin(a), cos(a)) * (fract(lg) - 0.5 - (vec2(hash(lid + 2.0), hash(lid + 3.0)) - 0.5) * 0.3) / 0.62;
    float lv;
    float lm = maple(lq, lv);
    vec3 lc = leafColor(hash(lid + 5.0 + fl)) * (0.6 + 0.3 * fl / 2.0 + 0.2 * hash(lid + 6.0));
    o = over(o, lc, lm * bed);
    o = over(o, lc * 0.6, lv * bed * 0.5);
  }
  gl_FragColor = o;
}`;

/** Pixel art — a campfire in the forest at night: twinkling stars and a crescent moon, mountains with snow
 * caps, two rows of pines, a tent lit on one side, a traveller sitting by the fire, the flames dancing
 * frame by frame, sparks and smoke rising, the firelight dithered on the ground, fireflies blinking. */
const PIXELCAMP = `${PIXEL}
float pine(vec2 px, float x0, float h) {
  float y = px.y;
  float w = (h - y) * 0.42 - mod(y, 7.0) * 0.6 + 2.0;
  return step(0.0, y) * step(y, h) * step(abs(px.x - x0), max(w, 0.0)) + step(abs(px.x - x0), 1.0) * step(y, 3.0) * step(-2.0, y);
}
void main() {
  float rows = 180.0;
  vec2 px = floor(gl_FragCoord.xy / u_res.y * rows);
  float W = floor(u_res.x / u_res.y * rows);
  float t = u_time;
  float tf = floor(t * 8.0) / 8.0;
  vec4 o = vec4(0.0);
  float gy = 30.0;
  // sky, dithered from deep blue to the purple of the horizon
  float sv = (px.y - 60.0) / 110.0;
  vec3 sky = sv < 0.5 ? dither(vec3(0.17, 0.11, 0.27), vec3(0.12, 0.09, 0.23), sv * 2.0, px) : dither(vec3(0.12, 0.09, 0.23), vec3(0.06, 0.07, 0.18), sv * 2.0 - 1.0, px);
  o = over(o, sky, 0.55);
  float sh = hash(px);
  float star = step(0.994, sh) * step(0.3, fract(sh * 91.0 + floor(t * 2.0 + sh * 10.0) * 0.37));
  vec2 bc = floor(px / 16.0);
  vec2 bs = bc * 16.0 + floor(vec2(hash(bc), hash(bc + 7.0)) * 14.0) + 1.0;
  vec2 bd = abs(px - bs);
  float big = step(0.75, hash(bc + 3.0)) * step(bd.x + bd.y, 1.0 + step(0.5, sin(t * 2.0 + hash(bc) * 30.0)));
  o = over(o, vec3(1.0, 0.95, 0.8), clamp(star + big, 0.0, 1.0) * step(90.0, px.y));
  vec2 moon = vec2(floor(W * 0.82), 150.0);
  float m = step(length(px - moon), 9.0) * step(5.5, length(px - moon - vec2(4.0, 3.0)));
  o = over(o, vec3(1.0, 0.95, 0.72), m);
  // mountains with snow caps
  float peak = 60.0 + 26.0 * abs(fract(px.x / 70.0 + 0.3) - 0.5) * -2.0 + 26.0 + 8.0 * hash(vec2(floor(px.x / 70.0 + 0.3), 1.0));
  float mount = step(px.y, peak);
  o = over(o, mix(vec3(0.16, 0.13, 0.26), vec3(0.8, 0.82, 0.95), step(peak - 5.0, px.y)), mount);
  // pines, the far row bluer
  float far = 0.0;
  float cell = floor(px.x / 13.0);
  far = pine(vec2(px.x, px.y - gy - 4.0), cell * 13.0 + 6.0 + floor(hash(vec2(cell, 2.0)) * 3.0), 22.0 + floor(hash(vec2(cell, 3.0)) * 18.0));
  o = over(o, vec3(0.1, 0.16, 0.2), clamp(far, 0.0, 1.0));
  float near = 0.0;
  float c2 = floor((px.x + 9.0) / 23.0);
  float keep = step(0.45, hash(vec2(c2, 4.0)));
  near = pine(vec2(px.x, px.y - gy + 1.0), c2 * 23.0 - 9.0 + 11.0, 34.0 + floor(hash(vec2(c2, 5.0)) * 22.0)) * keep;
  float fireX = floor(W * 0.55);
  near *= step(40.0, abs(px.x - fireX));
  o = over(o, vec3(0.04, 0.09, 0.08), clamp(near, 0.0, 1.0));
  // the ground, the firelight on it
  float ground = step(px.y, gy);
  o = over(o, dither(vec3(0.05, 0.1, 0.07), vec3(0.08, 0.15, 0.09), hash(floor(px / 2.0)) * 0.6, px), ground);
  float flick = 0.08 * sin(t * 9.0) + 0.05 * sin(t * 23.0);
  float light = 1.0 - length((px - vec2(fireX, gy + 4.0)) * vec2(1.0, 1.8)) / (62.0 + flick * 30.0);
  o = over(o, vec3(1.0, 0.55, 0.2), step(bayer4(px), light * 0.7) * 0.28);
  // the tent, its side facing the fire lit
  float tx = floor(W * 0.36);
  vec2 tq = px - vec2(tx, gy);
  float tent = step(0.0, tq.y) * step(abs(tq.x), 20.0 - tq.y * 0.8);
  float door = step(0.0, tq.y) * step(abs(tq.x - 2.0), 6.0 - tq.y * 0.4) * step(tq.y, 14.0);
  o = over(o, tq.x > 0.0 ? vec3(0.85, 0.45, 0.2) : vec3(0.45, 0.22, 0.12), tent);
  o = over(o, vec3(0.12, 0.05, 0.04), door * tent);
  o = over(o, vec3(0.3, 0.18, 0.1), step(abs(tq.x), 0.5) * step(tq.y, 27.0) * step(25.0, tq.y));
  // the traveller on a log, warm on the fire side
  vec2 sq = px - vec2(fireX - 20.0, gy);
  float log_ = step(abs(sq.x), 7.0) * step(0.0, sq.y) * step(sq.y, 2.0);
  float bodyM = step(abs(sq.x), 3.0) * step(3.0, sq.y) * step(sq.y, 11.0);
  float head = step(length(sq - vec2(0.0, 14.0)), 2.6);
  o = over(o, vec3(0.32, 0.18, 0.1), log_);
  o = over(o, mix(vec3(0.3, 0.2, 0.35), vec3(1.0, 0.6, 0.3), step(2.0, sq.x)), clamp(bodyM + head, 0.0, 1.0));
  o = over(o, vec3(0.7, 0.2, 0.2), step(abs(sq.x), 3.0) * step(abs(sq.y - 11.0), 0.5)); // a scarf
  o = over(o, vec3(0.3, 0.2, 0.35), step(abs(sq.x - 4.0 - 0.0), 3.0) * step(abs(sq.y - 7.0 + (sq.x - 4.0) * 0.3), 0.6)); // an arm to the fire
  // the fire: stones, logs, flames frame by frame
  vec2 fq = px - vec2(fireX, gy);
  float stones = step(abs(fq.y - 1.0), 1.0) * step(9.0, abs(fq.x)) * step(abs(fq.x), 12.0) * step(0.3, hash(vec2(floor(fq.x / 2.0), 9.0)));
  o = over(o, vec3(0.45, 0.45, 0.5), stones);
  float logs = step(abs(fq.y - 2.0 - fq.x * 0.25), 1.0) * step(abs(fq.x), 8.0) + step(abs(fq.y - 2.0 + fq.x * 0.25), 1.0) * step(abs(fq.x), 8.0);
  o = over(o, vec3(0.35, 0.18, 0.08), clamp(logs, 0.0, 1.0));
  float fh = 24.0 * (1.0 - abs(fq.x) / 12.0) + 4.0 * sin(tf * 7.0 + fq.x * 0.7);
  float flame = (1.0 - (fq.y - 3.0) / max(fh, 1.0)) + (noise(vec2(fq.x * 0.35, fq.y * 0.25 - tf * 5.0)) - 0.5) * 0.9;
  flame *= step(3.0, fq.y) * step(abs(fq.x), 12.0);
  vec3 fc = flame > 0.8 ? vec3(1.0, 0.96, 0.7) : flame > 0.55 ? vec3(1.0, 0.8, 0.2) : flame > 0.35 ? vec3(1.0, 0.45, 0.1) : vec3(0.8, 0.15, 0.05);
  o = over(o, fc, step(0.18, flame));
  // smoke and sparks rising
  for (int i = 0; i < 9; i++) {
    float fi = float(i);
    float ph = fract(hash(vec2(fi, 1.0)) + t * (0.25 + 0.2 * hash(vec2(fi, 2.0))));
    vec2 s = vec2(fireX + floor(sin(ph * 9.0 + fi) * 6.0), gy + 18.0 + floor(ph * 60.0));
    o = over(o, vec3(1.0, 0.7, 0.25), step(length(px - s), 0.6) * step(0.4, fract(t * 3.0 + fi * 0.3)) * (1.0 - ph));
  }
  float sm = noise(vec2(px.x * 0.12 - t * 0.3, px.y * 0.08 - t * 0.6));
  float column = smoothstep(14.0, 0.0, abs(px.x - fireX - (px.y - gy - 26.0) * 0.35)) * step(gy + 26.0, px.y) * smoothstep(110.0, 50.0, px.y);
  o = over(o, vec3(0.55, 0.55, 0.6), step(bayer4(px), sm * column * 0.7) * 0.5);
  // fireflies among the pines
  vec2 ff = floor(px / 9.0);
  vec2 fp = ff * 9.0 + floor(vec2(hash(ff + 1.0), hash(ff + 2.0)) * 8.0) + floor(vec2(sin(t + hash(ff) * 9.0), cos(t * 0.8 + hash(ff) * 7.0)) * 1.5);
  float fly = step(0.93, hash(ff + 4.0)) * step(length(px - fp), 0.6) * step(0.5, sin(t * 2.0 + hash(ff) * 20.0)) * step(gy, px.y) * step(px.y, 75.0);
  o = over(o, vec3(0.8, 1.0, 0.4), fly);
  gl_FragColor = o;
}`;

/** Pixel art — a sunset beach: a sky in dithered bands, a striped sun sinking, flat pink clouds drifting,
 * the sun's reflection glittering on the sea, waves rolling in with foam, a palm tree swaying against the
 * light, gulls flapping by and a sailboat on the horizon. */
const PIXELBEACH = `${PIXEL}
void main() {
  float rows = 180.0;
  vec2 px = floor(gl_FragCoord.xy / u_res.y * rows);
  float W = floor(u_res.x / u_res.y * rows);
  float t = u_time;
  float tf = floor(t * 6.0) / 6.0;
  vec4 o = vec4(0.0);
  float hz = 70.0;
  // the sky: five bands, dithered between them
  float v = clamp((px.y - hz) / (rows - hz), 0.0, 1.0) * 4.0;
  float band = floor(v);
  vec3 c0 = band < 1.0 ? vec3(1.0, 0.85, 0.5) : band < 2.0 ? vec3(1.0, 0.62, 0.3) : band < 3.0 ? vec3(0.95, 0.4, 0.38) : vec3(0.55, 0.22, 0.45);
  vec3 c1 = band < 1.0 ? vec3(1.0, 0.62, 0.3) : band < 2.0 ? vec3(0.95, 0.4, 0.38) : band < 3.0 ? vec3(0.55, 0.22, 0.45) : vec3(0.22, 0.12, 0.35);
  o = over(o, dither(c0, c1, smoothstep(0.55, 1.0, fract(v)), px), step(hz, px.y) * 0.5);
  // the sun, striped as it sinks
  vec2 sun = vec2(floor(W * 0.62), hz + 12.0);
  float ds = length(px - sun);
  float below = sun.y + 4.0 - px.y;
  float gaps = step(0.0, below) * step(mod(px.y, 5.0), clamp(below / 6.0, 0.0, 3.0));
  float disc = step(ds, 22.0) * (1.0 - gaps) * step(hz, px.y);
  o = over(o, dither(vec3(1.0, 0.5, 0.25), vec3(1.0, 0.92, 0.45), (px.y - sun.y + 22.0) / 44.0, px), disc);
  // flat clouds lit pink from below
  float cn = noise(vec2(px.x * 0.025 + t * 0.03, floor(px.y / 3.0) * 0.4));
  float cloud = step(0.62, cn) * step(115.0, px.y) * step(px.y, 160.0);
  float lit = step(0.62, noise(vec2(px.x * 0.025 + t * 0.03, floor((px.y - 3.0) / 3.0) * 0.4)));
  o = over(o, lit < 0.5 ? vec3(1.0, 0.65, 0.6) : vec3(0.6, 0.3, 0.5), cloud);
  // the sea, the sun's reflection glittering on it
  float sea = step(px.y, hz - 1.0) * step(26.0, px.y);
  float deep = (hz - px.y) / 44.0;
  o = over(o, dither(vec3(0.5, 0.25, 0.45), vec3(0.15, 0.12, 0.32), deep, px), sea * 0.8);
  float wv = step(0.86, fract((px.y + tf * 4.0) / 7.0)) * step(0.55, noise(vec2(px.x * 0.08 + tf, px.y)));
  o = over(o, vec3(0.75, 0.45, 0.6), wv * sea);
  float spread = 24.0 - deep * 6.0;
  float glitter = step(abs(px.x - sun.x), spread) * step(0.45, hash(vec2(floor((px.x + px.y * 3.0) / 4.0), px.y + floor(t * 4.0))));
  o = over(o, mix(vec3(1.0, 0.65, 0.3), vec3(1.0, 0.9, 0.5), step(0.8, hash(px + tf))), glitter * sea * step(mod(px.y, 2.0), 0.5));
  // the sailboat on the horizon
  float bx = mod(W * 0.2 + t * 2.0, W + 40.0) - 20.0;
  vec2 bq = px - vec2(floor(bx), hz);
  float hull = step(abs(bq.x), 6.0 - max(0.0, -bq.y) ) * step(-2.0, bq.y) * step(bq.y, 0.0);
  float sail = step(1.0, bq.y) * step(bq.y, 13.0) * step(0.0, bq.x + 1.0) * step(bq.x, (13.0 - bq.y) * 0.5);
  o = over(o, vec3(0.2, 0.08, 0.2), clamp(hull + sail, 0.0, 1.0));
  // the waves running up the sand, foam at their edge
  float reach = 26.0 + floor(4.0 * (0.5 + 0.5 * sin(t * 0.6)) + 2.0 * sin(px.x * 0.06 + t * 0.4));
  float sand = step(px.y, reach);
  o = over(o, dither(vec3(0.95, 0.68, 0.45), vec3(0.85, 0.52, 0.38), (reach - px.y) / 26.0 + hash(px) * 0.2, px), sand * 0.9);
  float wet = step(px.y, reach) * step(reach - 4.0, px.y);
  o = over(o, vec3(0.7, 0.45, 0.4), wet * 0.6);
  float foam = step(abs(px.y - reach - 1.0), 1.0) * step(0.35, hash(vec2(floor(px.x / 2.0), floor(t * 5.0))));
  o = over(o, vec3(1.0, 0.92, 0.88), foam);
  // the palm tree against the light
  float px0 = floor(W * 0.14);
  float sway = sin(t * 1.1) * 0.08 + sin(t * 2.3) * 0.03;
  float ty = px.y - 20.0;
  float cx = px0 + 0.0022 * ty * ty + sway * ty * 0.1;
  float trunk = step(0.0, ty) * step(ty, 95.0) * step(abs(px.x - cx), 2.5 - ty * 0.008) * (0.7 + 0.3 * step(1.0, mod(ty, 5.0)));
  vec2 top = vec2(px0 + 0.0022 * 95.0 * 95.0 + sway * 9.5, 115.0);
  float fronds = 0.0;
  for (int i = 0; i < 7; i++) {
    float fi = float(i);
    float a = -2.6 + fi * 0.86 + sway * 2.0 + sin(t * 1.7 + fi) * 0.05;
    vec2 dir = vec2(cos(a), sin(a) * 0.6 + 0.35);
    vec2 rel = px - top;
    float L = 30.0 + 6.0 * hash(vec2(fi, 1.0));
    float s = clamp(dot(rel, dir) / L, 0.0, 1.0);
    vec2 on = dir * s * L - vec2(0.0, s * s * L * 0.55);
    float thick = (1.0 - s) * 3.5 + 0.8 + step(0.5, fract(s * 9.0)) * (1.0 - s) * 2.0;
    fronds += step(length(rel - on), thick) * step(0.02, s);
  }
  o = over(o, vec3(0.15, 0.07, 0.15), clamp(trunk + fronds + step(length(px - top), 3.5), 0.0, 1.0));
  // gulls flapping by
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float gx = mod(t * (8.0 + fi * 3.0) + fi * 90.0, W + 30.0) - 15.0;
    vec2 g = px - vec2(floor(gx), floor(130.0 + fi * 12.0 + sin(t + fi) * 4.0));
    float flap = step(0.5, fract(t * 2.5 + fi * 0.3));
    float wing = step(abs(g.x), 4.0) * step(abs(g.y - floor(abs(g.x) * (flap > 0.5 ? 0.6 : -0.3))), 0.5);
    o = over(o, vec3(0.2, 0.1, 0.22), wing);
  }
  gl_FragColor = o;
}`;

/** Pixel art — hot-air balloons over the countryside: a sunny sky, puffy clouds drifting, striped balloons
 * rising and bobbing with their baskets and burners puffing, hills in patchwork with little red-roofed
 * houses and a windmill turning. */
const PIXELBALLOONS = `${PIXEL}
void main() {
  float rows = 180.0;
  vec2 px = floor(gl_FragCoord.xy / u_res.y * rows);
  float W = floor(u_res.x / u_res.y * rows);
  float t = u_time;
  vec4 o = vec4(0.0);
  o = over(o, dither(vec3(0.62, 0.82, 1.0), vec3(0.36, 0.6, 0.95), (px.y - 40.0) / 140.0, px), 0.5);
  // the sun and its turning rays
  vec2 sun = vec2(floor(W * 0.88), 155.0);
  vec2 sd = px - sun;
  float sa = atan(sd.y, sd.x) + floor(t * 4.0) * 0.06;
  float rays = step(length(sd), 18.0) * step(12.0, length(sd)) * step(0.5, fract(sa * 8.0 / 6.2831));
  o = over(o, vec3(1.0, 0.88, 0.35), clamp(step(length(sd), 9.0) + rays, 0.0, 1.0));
  // puffy clouds made of round blobs, drifting
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    float cx = mod(hash(vec2(fi, 1.0)) * W + t * (2.0 + fi), W + 60.0) - 30.0;
    vec2 c = vec2(floor(cx), floor(95.0 + 70.0 * hash(vec2(fi, 2.0))));
    vec2 q = px - c;
    float cl = max(max(step(length(q), 7.0), step(length(q - vec2(8.0, -2.0)), 6.0)), max(step(length(q - vec2(-8.0, -2.0)), 5.0), step(length(q - vec2(15.0, -4.0)), 4.0)));
    cl = max(cl, step(abs(q.x - 3.0), 17.0) * step(abs(q.y + 5.0), 2.0));
    float shade = step(q.y, -5.0);
    o = over(o, shade > 0.5 ? vec3(0.78, 0.86, 0.98) : vec3(1.0), cl * 0.95);
  }
  // the hills: far green, near patchwork
  float h1 = 52.0 + floor(10.0 * sin(px.x * 0.02 + 1.0) + 5.0 * sin(px.x * 0.05));
  o = over(o, vec3(0.45, 0.72, 0.4), step(px.y, h1));
  float h2 = 34.0 + floor(8.0 * sin(px.x * 0.015 + 3.0) + 4.0 * sin(px.x * 0.043 + 1.0));
  vec2 fq = floor(vec2(px.x + px.y * 1.5, px.y) / vec2(22.0, 7.0));
  float fh = hash(fq);
  vec3 fc = fh < 0.3 ? vec3(0.95, 0.82, 0.35) : fh < 0.6 ? vec3(0.4, 0.7, 0.3) : fh < 0.8 ? vec3(0.55, 0.8, 0.35) : vec3(0.75, 0.55, 0.32);
  vec2 fr = mod(vec2(px.x + px.y * 1.5, px.y), vec2(22.0, 7.0));
  fc = (fr.x < 1.0 || fr.y < 1.0) ? vec3(0.22, 0.45, 0.22) : fc;
  o = over(o, dither(fc, fc * 0.88, hash(floor(px / 2.0)) * 0.5, px), step(px.y, h2));
  // little houses on the far hill
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float hx = floor(W * (0.12 + fi * 0.22 + 0.05 * hash(vec2(fi, 3.0))));
    float hb = 52.0 + floor(10.0 * sin(hx * 0.02 + 1.0) + 5.0 * sin(hx * 0.05)) - 1.0;
    vec2 q = px - vec2(hx, hb);
    float wall = step(abs(q.x), 3.0) * step(0.0, q.y) * step(q.y, 4.0);
    float roof = step(5.0, q.y) * step(abs(q.x), 4.0 - (q.y - 5.0)) * step(q.y, 8.0);
    o = over(o, vec3(1.0, 0.95, 0.85), wall);
    o = over(o, vec3(0.85, 0.2, 0.15), roof);
    o = over(o, vec3(0.35, 0.25, 0.2), wall * step(abs(q.x - 1.0), 0.5) * step(q.y, 2.0));
  }
  // the windmill, its sails turning
  vec2 wm = vec2(floor(W * 0.72), 0.0);
  wm.y = 52.0 + floor(10.0 * sin(wm.x * 0.02 + 1.0) + 5.0 * sin(wm.x * 0.05));
  vec2 wq = px - wm;
  float tower = step(0.0, wq.y) * step(wq.y, 18.0) * step(abs(wq.x), 4.0 - wq.y * 0.12);
  o = over(o, vec3(0.95, 0.92, 0.85), tower);
  vec2 hub = wq - vec2(0.0, 18.0);
  float wa = floor(t * 6.0) * 0.12;
  float sails = 0.0;
  for (int i = 0; i < 4; i++) {
    float a = wa + float(i) * 1.5708;
    vec2 dir = vec2(cos(a), sin(a));
    float along = dot(hub, dir);
    float across = abs(dot(hub, vec2(-dir.y, dir.x)) - 1.5);
    sails += step(0.0, along) * step(along, 14.0) * step(across, 1.6);
  }
  o = over(o, vec3(0.55, 0.35, 0.25), clamp(sails, 0.0, 1.0));
  o = over(o, vec3(0.3, 0.2, 0.15), step(length(hub), 1.6));
  // the balloons: striped envelopes, ropes, baskets, a burner puffing now and then
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    float R = 8.0 + floor(8.0 * hash(vec2(fi, 4.0)));
    float rise = fract(hash(vec2(fi, 5.0)) + t * (0.006 + 0.006 * hash(vec2(fi, 6.0))));
    vec2 c = vec2(floor(mod(W * hash(vec2(fi, 7.0)) + t * (1.5 + fi * 0.6), W + 40.0) - 20.0),
                  floor(40.0 + rise * 170.0 + 2.0 * sin(t * 0.8 + fi)));
    vec2 q = px - c;
    float env = step(length(q * vec2(1.0, 0.9)), R) + step(abs(q.x), R * 0.55 * (1.0 + q.y / R)) * step(-R * 1.3, q.y) * step(q.y, 0.0);
    env = clamp(env, 0.0, 1.0);
    float stripe = mod(floor((q.x / R + 1.0) * 3.0), 2.0);
    float pick = hash(vec2(fi, 8.0));
    vec3 ca = pick < 0.33 ? vec3(0.95, 0.3, 0.3) : pick < 0.66 ? vec3(0.3, 0.55, 0.95) : vec3(0.98, 0.75, 0.2);
    vec3 cb = pick < 0.5 ? vec3(1.0, 0.95, 0.85) : vec3(0.35, 0.8, 0.5);
    vec3 col = stripe > 0.5 ? ca : cb;
    col *= q.x > R * 0.45 ? 0.8 : 1.0;
    col = length(q - vec2(-R * 0.4, R * 0.45)) < R * 0.18 ? vec3(1.0) : col;
    o = over(o, col, env);
    float basketY = -R * 1.3 - 6.0;
    float ropes = step(abs(abs(q.x) - 2.0 - (q.y - basketY) * 0.1), 0.5) * step(basketY + 3.0, q.y) * step(q.y, -R * 1.3);
    float basket = step(abs(q.x), 2.5) * step(abs(q.y - basketY), 1.5);
    float burn = step(0.85, hash(vec2(fi, floor(t * 3.0)))) * step(abs(q.x), 1.0) * step(abs(q.y - basketY - 5.0), 1.0);
    o = over(o, vec3(0.35, 0.25, 0.2), ropes);
    o = over(o, vec3(0.6, 0.38, 0.2), basket);
    o = over(o, vec3(1.0, 0.65, 0.2), burn);
  }
  gl_FragColor = o;
}`;

export const COZY_SHADERS: Record<string, string> = {
  goldenhour: GOLDENHOUR,
  windowrain: WINDOWRAIN,
  summerfield: SUMMERFIELD,
  soapbubbles: SOAPBUBBLES,
  skylanterns: SKYLANTERNS,
  autumnlane: AUTUMNLANE,
  pixelcamp: PIXELCAMP,
  pixelbeach: PIXELBEACH,
  pixelballoons: PIXELBALLOONS,
};
