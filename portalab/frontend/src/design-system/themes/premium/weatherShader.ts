import { COMMON } from "./shaders";

/**
 * #88: the shared noise made safe for phones whose GPU computes at a lower precision (seen on a Mali chip:
 * the clouds broke into facets with a seam down the middle) — the cells' coordinates folded to small
 * numbers before hashing, a hash that never multiplies them by large factors.
 */
export const SAFE_COMMON = COMMON.replace(
  /float hash\(vec2 p\) \{[\s\S]*?\n\}/,
  `float hash(vec2 p) {
  p = mod(p, 289.0);
  p = fract(p * 0.3183099 + vec2(0.71, 0.113)) * 17.0;
  return fract(p.x * p.y * (p.x + p.y));
}`,
).replace("vec2 i = floor(p);", "vec2 i = mod(floor(p), 289.0);");

/**
 * #88: « live weather » — one scene drawn from the weather report's numbers (``weatherScene.ts``), so every
 * sky has its look and they blend as the weather turns: the light of the hour (a pink dawn, a blue day, an
 * orange dusk, a night of stars and the moon in its phase), clouds from a few wisps to a heavy overcast
 * drifting with the wind, a milky veil of high clouds with the sun's halo, mist and fog banks, drizzle, rain in streaks or curtains of showers, snow from flakes to
 * grains settling at the bottom, bouncing hail, lightning lighting the clouds, gusts of wind, frost creeping
 * on the edges when it freezes. Premultiplied over the page, light enough to read through.
 */
export const WEATHER = `${SAFE_COMMON}
uniform float u_light;
uniform float u_glow;
uniform float u_dawn;
uniform float u_cloud;
uniform float u_veil;
uniform float u_dark;
uniform float u_rain;
uniform float u_drizzle;
uniform float u_burst;
uniform float u_snow;
uniform float u_grains;
uniform float u_hail;
uniform float u_ice;
uniform float u_fog;
uniform float u_bolt;
uniform float u_wind;
uniform float u_windDir;
uniform float u_moon;
uniform float u_paper;   // 1 over a light page: what is white is drawn a little darker to show

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

// a jagged bolt down from the clouds
float bolt(vec2 p, float x0, float top, float seed, float width) {
  float x = x0 + (fbm4(vec2(p.y * 2.2, seed)) - 0.5) * 0.5 + (noise(vec2(p.y * 18.0, seed * 3.0)) - 0.5) * 0.05;
  float d = abs(p.x - x);
  float along = smoothstep(top, top + 0.04, p.y) * step(p.y, 1.05);
  return along * (smoothstep(width, 0.0, d) + exp(-d * 55.0) * 0.35);
}

void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);                     // small numbers, for GPUs of lower precision
  float aspect = u_res.x / u_res.y;
  float night = 1.0 - u_light;
  float gust = 0.7 + 0.2 * sin(t * 0.63) + 0.1 * sin(t * 1.71 + 1.3);
  float blow = u_wind * gust * u_windDir;            // signed: where things drift
  float drift = 0.022 + 0.09 * u_wind;               // the clouds' pace

  // the sky of the hour, faint so the page reads through
  vec3 top = mix(vec3(0.03, 0.05, 0.16), vec3(0.24, 0.47, 0.88), u_light);
  vec3 low = mix(vec3(0.08, 0.12, 0.26), vec3(0.58, 0.76, 0.96), u_light);
  vec3 warm = mix(vec3(1.0, 0.5, 0.22), vec3(1.0, 0.58, 0.62), u_dawn);
  low = mix(low, warm, u_glow * 0.8);
  top = mix(top, mix(vec3(0.24, 0.16, 0.42), vec3(0.32, 0.36, 0.66), u_dawn), u_glow * 0.55);
  vec3 sky = mix(low, top, smoothstep(0.0, 1.0, uv.y));
  vec3 grey = mix(vec3(0.07, 0.08, 0.1), vec3(0.6, 0.63, 0.68), u_light * (1.0 - 0.55 * u_dark) + u_glow * 0.15);
  sky = mix(sky, grey, u_cloud * 0.8);
  sky = mix(sky, sky * vec3(0.86, 0.94, 1.08), u_ice);
  float skyA = 0.2 + 0.1 * u_cloud + 0.08 * u_glow + 0.1 * u_paper;
  vec4 o = vec4(sky * skyA, skyA);

  // where the sun stands: high by day, low and warm at dawn (left) and dusk (right)
  float sunVis = (u_light * (1.0 - u_glow) + u_glow * 0.9) * (1.0 - u_cloud * 0.8) * (1.0 - u_fog * 0.7);
  vec2 sc = mix(vec2(0.78 * aspect, 0.82), vec2(mix(0.84, 0.16, u_dawn) * aspect, 0.14), u_glow);
  float sd = length(p - sc);
  vec3 sunCore = mix(vec3(1.0, 0.98, 0.9), vec3(1.0, 0.78, 0.5), u_glow);
  vec3 sunHalo = mix(vec3(1.0, 0.85, 0.5), vec3(1.0, 0.48, 0.22), u_glow);
  sunHalo = mix(sunHalo, sunHalo * vec3(1.0, 0.8, 0.55), u_paper * 0.6);   // warmer to show on a light page

  // stars and the moon, behind the clouds
  float clearNight = night * (1.0 - u_cloud * 0.9) * (1.0 - u_fog);
  if (clearNight > 0.01) {
    for (int i = 0; i < 2; i++) {
      float fi = float(i);
      vec2 sg = p * (70.0 + fi * 60.0) + fi * 17.0;
      float sh = hash(floor(sg));
      vec2 jit = vec2(hash(floor(sg) + 3.7), hash(floor(sg) + 8.1)) - 0.5;
      float star = step(0.985 + fi * 0.005, sh) * smoothstep(0.22 - fi * 0.06, 0.0, length(fract(sg) - 0.5 - jit * 0.5))
        * (0.55 + 0.45 * sin(t * (1.6 + fi) + sh * 60.0)) * smoothstep(0.15, 0.6, uv.y);
      o = over(o, mix(vec3(1.0, 0.95, 0.85), vec3(0.8, 0.88, 1.0), hash(floor(sg) + 1.1)), star * clearNight * (1.0 - fi * 0.35));
    }
    float band = exp(-abs(uv.y - 0.55 - (p.x / aspect - 0.5) * 0.5) * 7.0) * fbm4(p * 4.0 + vec2(t * 0.004, 0.0));
    o = over(o, vec3(0.55, 0.6, 0.85), band * 0.12 * clearNight);
    // now and then a shooting star streaks across
    float slotS = floor(t / 6.0);
    float lifeS = mod(t, 6.0) / 0.9;
    if (hash(vec2(slotS, 21.0)) > 0.45 && lifeS < 1.0) {
      vec2 from = vec2((0.15 + 0.6 * hash(vec2(slotS, 22.0))) * aspect, 0.65 + 0.3 * hash(vec2(slotS, 23.0)));
      vec2 way = normalize(vec2(0.8 + 0.4 * hash(vec2(slotS, 24.0)), -0.45));
      vec2 head = from + way * lifeS * 0.5;
      vec2 rel = p - head;
      float along = dot(rel, -way);
      float across = abs(dot(rel, vec2(-way.y, way.x)));
      float trail = smoothstep(0.0025, 0.0, across) * smoothstep(0.18, 0.0, along) * step(0.0, along);
      float flare = smoothstep(0.006, 0.0, length(rel));
      o = over(o, vec3(0.95, 0.97, 1.0), (trail * 0.8 + flare) * sin(lifeS * 3.1416) * clearNight);
    }
    // the moon: a sphere lit by the sun from where its phase says (waxing: lit on the right)
    vec2 mc = vec2(0.8 * aspect, 0.8);
    float md = length(p - mc);
    vec2 m = (p - mc) / 0.06;
    float r2 = dot(m, m);
    float disc = smoothstep(1.0, 0.86, r2);
    float ph = u_moon * 6.2832;
    float facing = dot(vec3(m, sqrt(max(0.0, 1.0 - r2))), vec3(sin(ph), 0.0, -cos(ph)));
    float lit = disc * smoothstep(-0.04, 0.1, facing);
    float full = 0.5 - 0.5 * cos(ph);
    vec3 moonCol = vec3(0.95, 0.93, 0.85) * (0.82 + 0.18 * fbm4(m * 2.6));
    float moonVis = smoothstep(0.55, 0.95, night) * (1.0 - u_cloud * 0.75) * (1.0 - u_fog * 0.8);
    o = over(o, vec3(0.2, 0.22, 0.3), disc * moonVis * 0.3);          // the dark side, faintly
    o = over(o, moonCol, lit * moonVis);
    float breathe = 0.85 + 0.15 * sin(t * 0.6);
    o = over(o, vec3(0.8, 0.85, 1.0), exp(-md * 9.0) * 0.25 * breathe * moonVis * (0.3 + 0.7 * full));
  }

  // the sun: a bright disc with a soft limb and a layered glow — no spikes; broad soft shafts of light only
  // where clouds break, a glow along the horizon at dawn and dusk, faint lens ghosts across a clear sky
  if (sunVis > 0.01) {
    float r = mix(0.048, 0.066, u_glow);
    float ang = atan(p.y - sc.y, p.x - sc.x);
    // the air glowing around it, wider and warmer when the sun is low — breathing slowly
    float pulse = 0.88 + 0.08 * sin(t * 0.9) + 0.04 * sin(t * 2.3 + 1.0);
    o = over(o, sunHalo, (exp(-sd * 3.0) * 0.26 * pulse + exp(-sd * 1.1) * (0.06 + 0.12 * u_glow)) * sunVis);
    // a living corona: a soft turbulent ring turning around the disc
    vec2 rd = (p - sc) / max(sd, 1e-3);
    float turn = t * 0.06;
    vec2 spun = vec2(rd.x * cos(turn) - rd.y * sin(turn), rd.x * sin(turn) + rd.y * cos(turn));
    float flame = fbm4(spun * 1.6 + vec2(0.0, sd * 5.0 - t * 0.25));
    float corona = exp(-max(sd - r, 0.0) * mix(18.0, 12.0, flame)) * smoothstep(r * 0.8, r * 1.1, sd);
    o = over(o, sunCore, corona * (0.3 + 0.25 * flame) * pulse * sunVis);
    o = over(o, sunCore, exp(-max(sd - r, 0.0) * 22.0) * 0.5 * pulse * sunVis);
    // crepuscular shafts: wide, soft, slowly turning, strongest under a broken sky
    float broken = clamp(u_cloud * (1.0 - u_cloud) * 4.0, 0.0, 1.0) * (1.0 - u_veil);
    vec2 dir = (p - sc) / max(sd, 1e-3);                 // the direction, not the angle: no seam
    float shaft = smoothstep(0.42, 0.9, noise(dir * 2.6 + vec2(t * 0.012, 1.7)))
      * (0.6 + 0.4 * noise(dir * 6.0 - vec2(t * 0.01, 4.2)));
    o = over(o, sunHalo, shaft * exp(-sd * 1.6) * smoothstep(r, r * 4.0, sd) * 0.18 * broken * sunVis);
    // the disc shimmers a little, as through warm air
    float heat = (noise(p * 40.0 + vec2(0.0, -t * 1.5)) - 0.5) * 0.006;
    float limb = smoothstep(r, r * 0.86, sd + heat);
    vec3 disc = mix(sunHalo, sunCore, smoothstep(r * 1.05, 0.0, sd) * 0.85 + 0.15);
    disc *= 0.95 + 0.05 * noise(p * 60.0 + t * 0.8);     // granulation drifting on its face
    o = over(o, disc, limb * sunVis * (1.0 - 0.45 * u_veil));
    // dawn and dusk: the low sun warms a band along the horizon
    float horizon = exp(-abs(uv.y - sc.y) * 7.0) * exp(-abs(p.x - sc.x) * 0.9) * u_glow;
    o = over(o, sunHalo, horizon * 0.28 * sunVis);
    // lens ghosts on the line from the sun through the middle of the sky
    vec2 mid = vec2(0.5 * aspect + 0.08 * sin(t * 0.13), 0.5 + 0.05 * cos(t * 0.11));  // the glare sways
    for (int i = 0; i < 3; i++) {
      float fi = float(i);
      vec2 g = sc + (mid - sc) * (0.7 + fi * 0.55);
      float gr = 0.02 + fi * 0.018;
      float ghost = smoothstep(gr, gr * 0.6, length(p - g)) * (0.5 + 0.5 * smoothstep(gr * 0.6, gr, length(p - g)));
      vec3 gc = mix(vec3(0.6, 0.85, 1.0), vec3(1.0, 0.75, 0.55), fi * 0.5);
      o = over(o, gc, ghost * 0.07 * u_light * (1.0 - u_glow) * (1.0 - u_cloud) * (1.0 - u_veil) * (1.0 - u_paper * 0.5));
    }
    // through a veil of high clouds: a milky glow and the halo ring around the sun
    float halo = smoothstep(0.03, 0.0, abs(sd - 0.3)) * (0.7 + 0.3 * sin(ang * 3.0 + t * 0.4)) * (0.85 + 0.15 * sin(t * 0.7));
    o = over(o, mix(vec3(0.95, 0.9, 1.0), vec3(1.0, 0.85, 0.7), u_glow), (halo * 0.35 + exp(-sd * 1.6) * 0.25) * u_veil * sunVis);
  }
  // a fair day: golden motes floating in the light, now and then a flock of birds crossing
  float fair = u_light * (1.0 - u_rain) * (1.0 - u_snow) * (1.0 - u_fog) * (1.0 - smoothstep(0.55, 0.85, u_cloud));
  if (fair + u_glow * 0.5 > 0.05) {
    vec2 mg = p * 7.0 + vec2(-t * (0.05 + 0.25 * u_wind) * u_windDir, t * 0.04);
    vec2 mid_ = floor(mg);
    vec2 mf = fract(mg) - 0.5 - (vec2(hash(mid_ + 1.3), hash(mid_ + 4.1)) - 0.5) * 0.7
      - 0.12 * vec2(sin(t * 0.7 + hash(mid_) * 9.0), cos(t * 0.5 + hash(mid_) * 7.0));
    float mote = step(0.82, hash(mid_ + 2.2)) * smoothstep(0.05, 0.0, length(mf))
      * (0.4 + 0.6 * sin(t * 1.3 + hash(mid_) * 30.0) * 0.5 + 0.3);
    o = over(o, sunHalo, mote * 0.45 * (fair + u_glow * 0.5) * (0.4 + 0.6 * exp(-sd * 1.5)));
  }
  if (fair > 0.2) {
    float period = 34.0;
    float k = floor(t / period);
    float life = mod(t, period) / 14.0;                  // crossing in 14 s, then a clear sky for a while
    if (life < 1.0 && hash(vec2(k, 31.0)) > 0.25) {
      float dirB = hash(vec2(k, 32.0)) > 0.5 ? 1.0 : -1.0;
      vec2 lead = vec2(mix(-0.1, aspect + 0.1, dirB > 0.0 ? life : 1.0 - life), 0.55 + 0.3 * hash(vec2(k, 33.0)) + 0.03 * sin(life * 6.0));
      for (int i = 0; i < 5; i++) {
        float fi = float(i);
        vec2 at = lead + vec2(-dirB * (0.03 + 0.03 * fi), -0.012 * fi * (mod(fi, 2.0) * 2.0 - 1.0) - 0.006 * fi);
        vec2 b = (p - at) * 60.0;
        float flap = 0.4 + 0.5 * sin(t * 9.0 + fi * 1.7);
        float wing = abs(b.y - abs(b.x) * flap + 0.2 * b.x * b.x * flap) ;
        float bird = smoothstep(0.45, 0.1, wing) * smoothstep(1.4, 1.0, abs(b.x));
        o = over(o, mix(vec3(0.12, 0.13, 0.18), vec3(0.2, 0.15, 0.2), u_glow), bird * 0.75 * fair);
      }
    }
  }

  // the veil itself: high, thin, streaked by the winds aloft
  if (u_veil > 0.01) {
    float fib = fbm4(vec2(p.x * 0.9 - t * 0.03 * u_windDir, p.y * 7.0 + fbm4(p * 1.5 + vec2(t * 0.01, 0.0)) * 1.5));
    float veil = smoothstep(0.25, 0.75, fib) * smoothstep(0.2, 0.75, uv.y);
    vec3 veilCol = mix(vec3(0.3, 0.32, 0.4), vec3(0.93, 0.94, 0.98), u_light + u_glow * 0.3);
    veilCol = mix(veilCol, warm, u_glow * 0.4);
    o = over(o, veilCol, (0.12 + 0.3 * veil) * u_veil);
  }

  // the clouds: two layers drifting with the wind, warped; their cover and their weight from the report
  float cover = u_cloud;
  if (cover > 0.01) {
    vec2 q = vec2(p.x * 1.2 - t * drift * u_windDir, p.y * 2.4);
    vec2 w = vec2(fbm4(q * 0.9 + t * 0.02), fbm4(q * 0.9 + vec2(5.0, -t * 0.015)));
    float c1 = fbm(q + w * 1.3);
    float c2 = fbm4(q * 2.2 + w * 1.8 - vec2(t * drift * 1.6 * u_windDir, 0.0));
    float n = c1 * 0.72 + c2 * 0.28;
    float thr = mix(0.58, 0.2, sqrt(cover));           // a few clouds already show at a fifth of cover
    float reach = mix(0.45, -0.1, cover);              // a heavy sky comes down the page
    float dense = smoothstep(thr, thr + 0.16, n) * smoothstep(reach, reach + 0.4, uv.y);
    vec3 belly = mix(vec3(0.16, 0.18, 0.25), vec3(0.42, 0.45, 0.52), u_light) * (1.0 - 0.5 * u_dark);
    vec3 crest = mix(vec3(0.34, 0.37, 0.48), vec3(0.97, 0.98, 1.0), u_light) * (1.0 - 0.4 * u_dark);
    crest = mix(crest, crest * vec3(0.74, 0.77, 0.84), u_paper);
    belly = mix(belly, belly * 0.8, u_paper);
    vec3 col = mix(belly, crest, smoothstep(0.35, 0.85, c2));
    col = mix(col, warm * 0.9, u_glow * 0.45 * smoothstep(0.6, 0.2, c2));   // lit from below at dawn, dusk
    col += vec3(0.15, 0.16, 0.2) * night * (1.0 - u_dark) * smoothstep(0.6, 0.9, c2);  // the moon on the rims
    // the sun behind a cloud lights its thin edges (a silver lining)
    float edgeLit = smoothstep(thr + 0.16, thr, n) * exp(-sd * 3.5) * (u_light + u_glow) * (1.0 - u_dark)
      * (1.0 - smoothstep(0.55, 0.9, cover)) * (1.0 - u_fog);
    col += sunHalo * edgeLit * 1.2;
    // under a heavy sky, brighter patches pass slowly as the clouds thin and thicken
    col *= 0.9 + 0.18 * smoothstep(0.3, 0.8, noise(vec2(p.x * 0.6 - t * 0.04 * u_windDir, p.y * 0.8 + t * 0.02))) * smoothstep(0.5, 1.0, cover);
    // lightning: strikes at random moments, the clouds flaring around them
    if (u_bolt > 0.01) {
      float slot = floor(t / 2.1);
      float ph = mod(t, 2.1);
      float strikes = step(1.0 - 0.6 * u_bolt, hash(vec2(slot, 3.1)));
      float flicker = exp(-ph * 10.0) + 0.8 * exp(-abs(ph - 0.16) * 22.0) + 0.4 * exp(-abs(ph - 0.31) * 30.0);
      float flash = strikes * flicker;
      float bx = (0.12 + 0.76 * hash(vec2(slot, 7.0))) * aspect;
      float near = exp(-length((p - vec2(bx, 0.8)) * vec2(1.0, 1.6)) * 2.2);
      col += vec3(0.6, 0.65, 0.9) * flash * (0.35 + 1.4 * near);
      float far = step(0.75, hash(vec2(floor(t / 1.3), 11.0))) * exp(-mod(t, 1.3) * 6.0);
      col += vec3(0.45, 0.5, 0.75) * far * exp(-length(p - vec2(hash(vec2(floor(t / 1.3), 2.0)) * aspect, 0.85)) * 3.0) * u_bolt;
      o = over(o, col, dense * (0.62 + 0.3 * cover));
      float life = strikes * exp(-ph * 3.2);
      float b = bolt(p, bx, 0.12, slot, 0.0035);
      float br = bolt(vec2(p.x - (0.62 - p.y) * 0.25, p.y), bx + 0.02, 0.42, slot + 4.0, 0.0022) * step(p.y, 0.62);
      float strike = (b + br * 0.7) * life * flicker;
      o = over(o, vec3(0.88, 0.92, 1.0), clamp(strike * 1.6, 0.0, 1.0));
      o = over(o, vec3(0.55, 0.6, 0.75), flash * 0.1);
    } else {
      o = over(o, col, dense * (0.55 + 0.35 * cover));
    }
  }

  // fog: banks drifting low and a veil over everything; rime tints it cold
  if (u_fog > 0.01) {
    float f = fbm4(vec2(p.x * 1.6 - t * (0.03 + 0.08 * u_wind) * u_windDir, p.y * 3.2 + sin(t * 0.1)));
    float bank = smoothstep(0.3, 0.75, f) * smoothstep(0.85, 0.05, uv.y);
    vec3 fogCol = mix(vec3(0.3, 0.32, 0.38), vec3(0.85, 0.87, 0.9), u_light * 0.8 + u_glow * 0.2);
    fogCol = mix(fogCol, vec3(0.8, 0.9, 1.0), u_ice * 0.5);
    float bank2 = smoothstep(0.35, 0.8, fbm4(vec2(p.x * 3.0 + t * 0.05 * u_windDir, p.y * 5.0 - t * 0.02)));
    float breath = 0.88 + 0.12 * sin(t * 0.25 + p.x * 1.5);   // the fog thickens and thins
    o = over(o, fogCol, u_fog * breath * (0.3 + 0.45 * bank + 0.2 * bank2 * smoothstep(0.6, 0.0, uv.y)));
  }

  // what falls slants with the wind
  float slant = 0.06 + 0.5 * u_wind * gust;
  float rainAmt = u_rain;
  float snowAmt = u_snow;
  if (u_burst > 0.01) {
    // showers: curtains coming and going across the page
    float curtain = smoothstep(0.3, 0.7, noise(vec2(p.x * 0.7 - t * (0.05 + 0.1 * u_wind) * u_windDir, t * 0.06)));
    float wave = 0.35 + 0.65 * smoothstep(-0.3, 0.6, sin(t * 0.21));
    float amt = mix(1.0, 0.45 + curtain * wave * 1.0, u_burst);
    rainAmt *= amt;
    snowAmt *= amt;
  }

  // rain: streaks in three depths (drizzle: short, fine and slow)
  if (rainAmt > 0.01) {
    vec3 dropCol = mix(vec3(0.42, 0.48, 0.6), vec3(0.75, 0.82, 0.94), u_light * 0.7 + 0.3);
    dropCol = mix(dropCol, vec3(0.85, 0.95, 1.0), u_ice * 0.6);
    dropCol = mix(dropCol, vec3(0.3, 0.4, 0.55), u_paper * 0.7);
    for (int i = 0; i < 3; i++) {
      float fi = float(i);
      float density = mix(28.0 + fi * 26.0, 60.0 + fi * 40.0, u_drizzle);
      float stretch = mix(3.5 + fi * 2.5, 12.0 + fi * 4.0, u_drizzle);
      float speed = mix(5.0 + fi * 2.0 + rainAmt * 2.0, 2.2 + fi * 0.7, u_drizzle);
      vec2 r = vec2((p.x + p.y * slant * u_windDir) * density, p.y * stretch + t * speed);
      vec2 id = floor(r);
      vec2 f = fract(r);
      float h2 = hash(id * 1.3 + fi * 7.0);
      float width = mix(0.04, 0.06, u_drizzle) * (1.0 - fi * 0.2);
      float shown = step(1.0 - (0.18 + 0.55 * rainAmt), hash(id + fi * 17.0));
      float drop = shown * smoothstep(width, 0.0, abs(f.x - 0.2 - 0.6 * h2))
        * smoothstep(0.0, 0.35, f.y) * smoothstep(1.0, mix(0.5, 0.8, u_drizzle) + 0.2 * h2, f.y);
      o = over(o, dropCol, drop * (0.5 - fi * 0.1));
    }
    // splashes on the ground
    if (u_drizzle < 0.5) {
      vec2 s = vec2(p.x * 9.0, 0.0);
      float born = hash(vec2(floor(s.x), floor(t * 1.7)));
      float age = fract(t * 1.7);
      float ring = abs(length(vec2(fract(s.x) - 0.5, (uv.y - 0.03) * 40.0)) - age * 0.4);
      float splash = step(1.0 - 0.5 * rainAmt, born) * smoothstep(0.03, 0.0, ring) * (1.0 - age) * step(uv.y, 0.07);
      o = over(o, dropCol, splash * 0.7);
    }
    float mist = fbm4(vec2(p.x * 2.0 - t * 0.1 * u_windDir, p.y * 3.0)) * smoothstep(0.3, 0.0, uv.y);
    o = over(o, vec3(0.6, 0.65, 0.72) * (0.5 + 0.5 * u_light), mist * 0.3 * rainAmt);
  }

  // snow: flakes in three depths swaying down (grains: tiny, many, quicker), settling at the bottom
  if (snowAmt > 0.01) {
    vec3 flakeCol = mix(vec3(0.78, 0.82, 0.92), vec3(1.0), u_light * 0.8 + 0.2);
    flakeCol = mix(flakeCol, vec3(0.55, 0.64, 0.78), u_paper * 0.75);
    for (int i = 0; i < 3; i++) {
      float fi = float(i);
      float density = mix(9.0 + fi * 7.0, 26.0 + fi * 14.0, u_grains);
      float speed = mix(0.35 + fi * 0.18, 0.9 + fi * 0.3, u_grains) * (1.0 + u_wind * 0.6);
      vec2 g = p * density;
      g.y += t * speed * density * 0.12;
      g.x += sin(t * 0.7 + g.y * 0.35 + fi * 2.0) * 0.35 - blow * t * 0.6 * density * 0.08 + g.y * slant * u_windDir * 0.5;
      vec2 id = floor(g);
      vec2 f = fract(g) - 0.5;
      vec2 c = vec2(hash(id + 3.1 + fi), hash(id + 7.7 + fi)) - 0.5;
      float size = mix(0.13 - fi * 0.025, 0.07, u_grains) * (0.7 + 0.6 * hash(id + 1.3));
      float shown = step(1.0 - (0.2 + 0.6 * snowAmt), hash(id + fi * 11.0));
      float flake = shown * smoothstep(size, size * 0.35, length(f - c * 0.6));
      o = over(o, flakeCol, flake * (0.85 - fi * 0.2));
    }
    // snow settling at the bottom: soft rolling drifts, brighter on their crests
    float edge = (0.02 + 0.05 * u_snow) * (0.55 + 0.9 * fbm4(vec2(p.x * 2.2, 3.0)));
    float drift_ = smoothstep(edge, edge - 0.03, uv.y);
    float crestLine = smoothstep(0.012, 0.0, abs(uv.y - edge + 0.008));
    vec3 drifted = mix(vec3(0.62, 0.68, 0.8), vec3(0.95, 0.97, 1.0), u_light * (1.0 - 0.3 * u_paper));
    o = over(o, drifted, drift_ * 0.75 * u_snow);
    o = over(o, vec3(1.0), crestLine * 0.35 * u_snow * (1.0 - u_paper));
  }

  // hail: pellets falling fast and bouncing off the ground
  if (u_hail > 0.01) {
    for (int i = 0; i < 2; i++) {
      float fi = float(i);
      float density = 11.0 + fi * 8.0;
      vec2 g = vec2((p.x + p.y * slant * u_windDir) * density, p.y * density * 0.7 + t * (7.0 + fi * 2.0));
      vec2 id = floor(g);
      vec2 f = fract(g) - 0.5;
      vec2 at = vec2(hash(id) - 0.5, hash(id + 9.1) - 0.5) * 0.7;   // anywhere in its cell: no rows
      float shown = step(1.0 - 0.4 * u_hail, hash(id + fi * 5.0 + 0.3));
      float stone = shown * smoothstep(0.16, 0.08, length((f - at) * vec2(1.0, 1.5)));
      vec3 hailCol = mix(vec3(0.92, 0.96, 1.0), vec3(0.5, 0.6, 0.75), u_paper * 0.7);
      o = over(o, hailCol, stone * (0.95 - fi * 0.2));
    }
    vec2 s = vec2(p.x * 14.0, 0.0);
    float cell = floor(s.x);
    float ph = fract(t * 1.3 + hash(vec2(cell, 2.0)));
    float hop = 0.02 + 0.06 * hash(vec2(cell, floor(t * 1.3))) * sin(ph * 3.1416);
    float bounce = smoothstep(0.08, 0.03, length(vec2(fract(s.x) - 0.5, (uv.y - hop) * 14.0)))
      * step(1.0 - 0.6 * u_hail, hash(vec2(cell, floor(t * 1.3 + hash(vec2(cell, 2.0))))));
    o = over(o, vec3(0.9, 0.95, 1.0), bounce * 0.8);
  }

  // gusts: fine streaks racing with the wind
  if (u_wind > 0.3) {
    float row = floor(p.y * 26.0);
    float lane = hash(vec2(row, 4.0));
    float x = fract(p.x * 0.8 - t * (0.6 + lane) * u_windDir * u_wind + lane * 7.0);
    float streak = step(0.6, lane) * smoothstep(0.0, 0.18, x) * smoothstep(0.26, 0.18, x)
      * smoothstep(0.5, 0.2, abs(fract(p.y * 26.0) - 0.5) * 4.0);
    o = over(o, mix(vec3(0.6, 0.65, 0.75), vec3(0.95), u_light), streak * (u_wind - 0.3) * 0.5 * gust);
  }

  // a strong wind carries leaves tumbling across the page
  if (u_wind > 0.45) {
    for (int i = 0; i < 2; i++) {
      float fi = float(i);
      vec2 lg = vec2(p.x * (3.0 + fi) - t * (0.6 + 0.4 * fi) * u_wind * u_windDir * 2.0, p.y * (3.0 + fi) + sin(t * 1.3 + p.x * 3.0) * 0.4);
      vec2 lid = floor(lg);
      vec2 lf = fract(lg) - 0.5 - (vec2(hash(lid + 5.0), hash(lid + 6.0)) - 0.5) * 0.6;
      float spin = t * (2.0 + 3.0 * hash(lid)) + hash(lid + 2.0) * 6.28;
      vec2 rl = vec2(lf.x * cos(spin) - lf.y * sin(spin), lf.x * sin(spin) + lf.y * cos(spin));
      float leaf = step(0.86, hash(lid + 9.0 + fi)) * smoothstep(0.012, 0.0, length(rl * vec2(1.0, 2.4)) - 0.05);
      vec3 leafCol = mix(vec3(0.72, 0.45, 0.16), vec3(0.45, 0.55, 0.2), hash(lid + 3.0));
      o = over(o, leafCol * (0.5 + 0.5 * u_light), leaf * 0.85 * smoothstep(0.45, 0.8, u_wind));
    }
  }

  // frost creeping in from the edges when it freezes
  if (u_ice > 0.01) {
    vec2 e = min(uv, 1.0 - uv) * vec2(aspect, 1.0);
    float border = min(e.x, e.y);
    // ragged ice ferns: a slow noise sets how far each patch reaches, a fine one draws its needles
    float reachIce = (0.04 + 0.12 * u_ice) * (0.35 + 1.1 * fbm4(p * 3.0));
    float needles = abs(fbm4(p * vec2(38.0, 30.0)) - 0.5) * 2.0;
    float frost = smoothstep(reachIce, 0.0, border) * (0.55 + 0.45 * smoothstep(0.7, 0.1, needles));
    vec3 iceCol = mix(vec3(0.86, 0.94, 1.0), vec3(0.55, 0.68, 0.85), u_paper * 0.7);
    o = over(o, iceCol, frost * 0.6 * u_ice);
    vec2 gc = floor(p * 90.0);
    float glint = step(0.96, hash(gc)) * pow(0.5 + 0.5 * sin(t * 2.5 + hash(gc + 1.7) * 40.0), 12.0);
    o = over(o, vec3(1.0), glint * frost * u_ice * (1.0 - u_paper * 0.6));
  }

  gl_FragColor = o;
}`;
