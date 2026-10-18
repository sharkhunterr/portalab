// Halloween — the booster stage in a graveyard, alive: clouds racing over a veiled moon, dead trees bending in
  // the wind, mist rolling, bats; monsters barely seen as shadows on the far ridge (a gaunt long-armed thing, a
  // horned beast with red eyes, tentacles behind the hill) that stand out black when lightning tears the sky;
  // a wraith drifting by (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  // lightning: once in a while, a double flash and a forked bolt
  float win = floor(t / 6.5);
  float since = (fract(t / 6.5) - (0.25 + 0.5 * hash(vec2(win, 1.0)))) * 6.5;
  float strikes = step(0.35, hash(vec2(win, 2.0)));
  float flash = strikes * step(0.0, since) * (exp(-since * 7.0) + 0.7 * exp(-max(since - 0.18, 0.0) * 9.0) * step(0.18, since));
  // the sky
  o = over(o, mix(vec3(0.02, 0.01, 0.04), vec3(0.15, 0.06, 0.2), smoothstep(-0.4, 0.6, c.y)), 1.0);
  o = over(o, vec3(0.75, 0.72, 1.0), flash * 0.45 * smoothstep(-0.3, 0.6, c.y));
  // the moon, clouds racing over it
  vec2 mc = c - vec2(0.48, 0.26);
  float moon = smoothstep(0.12, 0.115, length(mc));
  o = over(o, vec3(1.0, 0.93, 0.78) - fbm(mc * 14.0) * 0.35, moon);
  o = over(o, vec3(1.0, 0.82, 0.6), exp(-length(mc) * 5.5) * 0.3);
  vec2 cq = vec2(c.x * 2.2 - t * 0.07, c.y * 5.0);
  float cloud = smoothstep(0.45, 0.8, fbm(cq + fbm(cq * 0.7 + t * 0.03)));
  o = over(o, mix(vec3(0.06, 0.03, 0.09), vec3(0.6, 0.55, 0.75), flash), cloud * 0.75 * smoothstep(0.0, 0.25, c.y));
  // the bolt: forked, jagged, from the clouds to the far ridge
  float bx = (hash(vec2(win, 3.0)) - 0.5) * 1.4;
  float path = bx + 0.07 * (noise(vec2(c.y * 9.0, win)) - 0.5) + 0.025 * (noise(vec2(c.y * 40.0, win)) - 0.5);
  float bolt = smoothstep(0.004, 0.0, abs(c.x - path)) * step(-0.12, c.y);
  float bpath = path + (c.y - 0.15) * 0.6 + 0.02 * (noise(vec2(c.y * 35.0, win + 9.0)) - 0.5);
  float branch = smoothstep(0.003, 0.0, abs(c.x - bpath)) * step(0.0, c.y) * step(c.y, 0.15);
  o = over(o, vec3(0.92, 0.9, 1.0), (bolt + branch) * step(0.0, since) * step(since, 0.32) * strikes);
  o = over(o, vec3(0.6, 0.55, 1.0), exp(-abs(c.x - path) * 40.0) * step(-0.12, c.y) * flash * 0.5);
  // the far ridge, and what stands on it: barely seen, black against the lightning
  float ridge = -0.1 + 0.05 * sin(c.x * 2.6 + 1.0) + 0.02 * noise(vec2(c.x * 8.0, 3.0));
  vec3 shade = mix(vec3(0.06, 0.03, 0.08), vec3(0.0), flash);
  float seen = 0.4 + 0.6 * clamp(flash * 2.0, 0.0, 1.0);
  o = over(o, shade, smoothstep(0.004, 0.0, c.y - ridge) * 0.9);
  // the gaunt one: tall, thin, long arms swaying, drifting along the ridge
  vec2 g = c - vec2(-0.3 + 0.06 * sin(t * 0.07), ridge + 0.0);
  float gb = smoothstep(0.006, 0.0, max(abs(g.x + g.y * 0.04) - 0.012, abs(g.y - 0.15) - 0.15));
  float gh = smoothstep(0.024, 0.02, length((g - vec2(0.0, 0.32)) * vec2(1.0, 0.8)));
  float sway = 0.02 * sin(t * 0.9);
  float arms = smoothstep(0.005, 0.0, abs(abs(g.x) - 0.03 - (0.28 - g.y) * 0.08 - sway * (0.28 - g.y))) * step(0.05, g.y) * step(g.y, 0.27);
  o = over(o, shade, clamp(gb + gh + arms, 0.0, 1.0) * seen);
  // the horned beast, crouched, its red eyes in the dark
  vec2 h = c - vec2(0.66, ridge);
  float hump = smoothstep(0.005, 0.0, length(h * vec2(0.8, 1.25) - vec2(0.0, 0.02)) - 0.07);
  float horns = smoothstep(0.004, 0.0, abs(h.x - 0.03 - (h.y - 0.08) * 0.5) - 0.006 * (0.2 - h.y) * 10.0) * step(0.07, h.y) * step(h.y, 0.15)
    + smoothstep(0.004, 0.0, abs(h.x + 0.03 + (h.y - 0.08) * 0.5) - 0.006 * (0.2 - h.y) * 10.0) * step(0.07, h.y) * step(h.y, 0.15);
  o = over(o, shade, clamp(hump + horns, 0.0, 1.0) * seen);
  float blink = step(0.07, fract(t * 0.23));
  float eyes = smoothstep(0.006, 0.002, length(h - vec2(-0.02, 0.075))) + smoothstep(0.006, 0.002, length(h - vec2(0.02, 0.075)));
  o = over(o, vec3(1.0, 0.1, 0.05), eyes * blink * (0.6 + 0.4 * sin(t * 2.0)));
  o = over(o, vec3(1.0, 0.1, 0.05), exp(-length(h - vec2(0.0, 0.075)) * 50.0) * 0.25 * blink);
  // tentacles rising behind the hill on the left, slowly waving
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    float base = -0.95 + fk * 0.09;
    float hgt = 0.18 + 0.08 * hash(vec2(fk, 5.0));
    float yy = c.y - ridge;
    float cx = base + 0.05 * sin(yy * 14.0 + t * (0.6 + 0.2 * fk) + fk) * yy * 4.0;
    float thick = mix(0.012, 0.002, clamp(yy / hgt, 0.0, 1.0));
    o = over(o, shade, smoothstep(thick, thick * 0.4, abs(c.x - cx)) * step(0.0, yy) * step(yy, hgt) * seen);
  }
  // the near ground, its stones, and a dead tree bending in the wind
  float ground = c.y + 0.32 + 0.03 * sin(c.x * 4.0);
  float stones = 0.0;
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    vec2 q = c - vec2(-0.85 + fk * 0.33 + 0.05 * hash(vec2(fk, 1.0)), -0.3);
    float hh = 0.07 + 0.05 * hash(vec2(fk, 2.0));
    float tomb = min(max(abs(q.x) - 0.04, q.y - hh), length(q - vec2(0.0, hh)) - 0.04);
    stones = max(stones, smoothstep(0.003, 0.0, max(tomb, -q.y - 0.05)));
  }
  vec2 tr = c - vec2(-0.6, -0.3);
  float bend = 0.04 * sin(t * 0.7) + 0.015 * sin(t * 2.1);
  tr.x -= bend * tr.y * tr.y * 5.0;
  float trunk = smoothstep(0.012, 0.004, abs(tr.x + 0.05 * tr.y * tr.y * 4.0)) * step(0.0, tr.y) * step(tr.y, 0.45);
  float br = smoothstep(0.008, 0.002, abs(tr.y - 0.3 - tr.x * (0.7 + 0.2 * sin(t * 1.3)))) * step(0.0, tr.x) * step(tr.x, 0.2)
    + smoothstep(0.007, 0.002, abs(tr.y - 0.22 + tr.x * (0.9 + 0.2 * sin(t * 1.1 + 1.0)))) * step(tr.x, 0.0) * step(-0.16, tr.x)
    + smoothstep(0.006, 0.002, abs(tr.y - 0.38 - tr.x * 1.6)) * step(0.0, tr.x) * step(tr.x, 0.07);
  o = over(o, vec3(0.008, 0.0, 0.015), max(max(stones, clamp(trunk + br, 0.0, 1.0)), smoothstep(0.004, 0.0, ground)));
  // eyes opening in the dark between the stones
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    vec2 ep = vec2(-0.7 + fk * 0.62 + 0.1 * hash(vec2(fk, 7.0)), -0.27 + 0.03 * hash(vec2(fk, 8.0)));
    float awake = smoothstep(0.55, 0.75, sin(t * (0.21 + 0.05 * fk) + fk * 2.3)) * step(0.06, fract(t * 0.37 + fk * 0.31));
    float pair = smoothstep(0.007, 0.003, length((c - ep - vec2(-0.016, 0.0)) * vec2(1.0, 2.2))) + smoothstep(0.007, 0.003, length((c - ep - vec2(0.016, 0.0)) * vec2(1.0, 2.2)));
    o = over(o, vec3(1.0, 0.85, 0.2), pair * awake);
  }
  // the mist, rolling in two layers
  float m1 = fbm(vec2(c.x * 2.2 + t * 0.09, c.y * 4.0 - t * 0.03));
  float m2 = fbm(vec2(c.x * 3.5 - t * 0.05, c.y * 6.0 + 3.0));
  o = over(o, vec3(0.45, 0.4, 0.58) + flash * 0.3, smoothstep(0.35, 0.8, m1) * smoothstep(0.05, -0.35, c.y) * 0.5);
  o = over(o, vec3(0.3, 0.26, 0.4), smoothstep(0.45, 0.85, m2) * smoothstep(-0.1, -0.4, c.y) * 0.45);
  // bats, flitting across
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    float run = fract(t * (0.05 + 0.04 * hash(vec2(fk, 3.0))) + hash(vec2(fk, 4.0)));
    vec2 b = vec2(-1.1 + run * 2.2, 0.08 + 0.38 * hash(vec2(fk, 5.0)) + 0.05 * sin(run * 30.0 + fk));
    vec2 q = (c - b) * (65.0 - 25.0 * hash(vec2(fk, 6.0)));
    float flap = sin(t * 15.0 + fk * 3.0);
    float wing = step(abs(q.x), 2.2) * smoothstep(0.35, 0.0, abs(q.y - abs(q.x) * 0.45 * flap - 0.25 * sin(abs(q.x) * 3.0)));
    o = over(o, vec3(0.0), clamp(wing + smoothstep(0.5, 0.3, length(q * vec2(1.4, 0.9))), 0.0, 1.0));
  }
  // a wraith drifting by: a pale veil with a long trailing tail and a hollow face, fading in and out
  float wph = fract(t / 23.0);
  vec2 wp = vec2(-1.0 + wph * 2.0, 0.08 + 0.06 * sin(t * 0.6));
  vec2 wq = c - wp;
  float tail = smoothstep(0.03, 0.0, abs(wq.y + 0.03 * sin(wq.x * 18.0 - t * 4.0) + wq.x * 0.25) - 0.02 * smoothstep(-0.25, 0.0, wq.x)) * smoothstep(-0.3, -0.14, wq.x) * step(wq.x, 0.02);
  float hood = smoothstep(0.035, 0.02, length(wq * vec2(1.0, 0.8)));
  float wraith = clamp(tail * (0.4 + 0.6 * smoothstep(-0.28, 0.0, wq.x)) + hood, 0.0, 1.0) * (0.55 + 0.45 * fbm(wq * 25.0 + t)) * smoothstep(0.0, 0.15, wph) * smoothstep(1.0, 0.85, wph);
  float hollow = smoothstep(0.007, 0.003, length(wq - vec2(-0.008, 0.004))) + smoothstep(0.007, 0.003, length(wq - vec2(0.01, 0.004))) + smoothstep(0.006, 0.002, length((wq - vec2(0.001, -0.014)) * vec2(1.4, 0.8)));
  o = over(o, vec3(0.78, 0.88, 0.95), wraith * 0.32);
  o = over(o, vec3(0.0), hollow * hood * 0.5 * smoothstep(0.0, 0.15, wph) * smoothstep(1.0, 0.85, wph));
  o.rgb *= mix(0.3, 1.0, smoothstep(1.1, 0.3, length(c * vec2(0.7, 1.0))));
