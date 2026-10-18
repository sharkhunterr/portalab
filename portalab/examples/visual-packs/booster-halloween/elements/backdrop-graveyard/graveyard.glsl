// Halloween — the booster stage in a graveyard: a violet sky, a veiled full moon, tombstones and a dead tree
  // against it, mist creeping low, bats flitting across (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, mix(vec3(0.03, 0.01, 0.05), vec3(0.16, 0.06, 0.22), smoothstep(-0.5, 0.6, c.y)), 1.0);
  // the moon, its veil of cloud passing
  vec2 mc = c - vec2(0.45, 0.25);
  float moon = smoothstep(0.13, 0.125, length(mc));
  float craters = fbm(mc * 14.0) * 0.35;
  o = over(o, vec3(1.0, 0.95, 0.8) - craters, moon);
  o = over(o, vec3(1.0, 0.85, 0.6), exp(-length(mc) * 6.0) * 0.35);
  float veil = smoothstep(0.45, 0.75, fbm(vec2(c.x * 3.0 - t * 0.04, c.y * 6.0)));
  o = over(o, vec3(0.12, 0.08, 0.16), veil * 0.55 * smoothstep(-0.1, 0.2, c.y));
  // tombstones and a dead tree, black against the sky
  float ground = c.y + 0.32 + 0.03 * sin(c.x * 4.0);
  float stones = 0.0;
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    float x = -0.85 + fk * 0.33 + 0.05 * hash(vec2(fk, 1.0));
    vec2 q = c - vec2(x, -0.3);
    float h = 0.07 + 0.05 * hash(vec2(fk, 2.0));
    float tomb = max(abs(q.x) - 0.04, q.y - h);
    tomb = min(tomb, length(q - vec2(0.0, h)) - 0.04);
    tomb = max(tomb, -q.y - 0.05);
    stones = max(stones, smoothstep(0.003, 0.0, tomb));
  }
  vec2 tr = c - vec2(-0.6, -0.3);
  float trunk = smoothstep(0.012, 0.004, abs(tr.x + 0.05 * tr.y * tr.y * 4.0)) * step(0.0, tr.y) * step(tr.y, 0.45);
  float branch = smoothstep(0.008, 0.002, abs(tr.y - 0.3 - (tr.x) * 0.7)) * step(0.0, tr.x) * step(tr.x, 0.18)
    + smoothstep(0.007, 0.002, abs(tr.y - 0.22 + (tr.x) * 0.9)) * step(tr.x, 0.0) * step(-0.15, tr.x);
  float black = max(max(stones, clamp(trunk + branch, 0.0, 1.0)), smoothstep(0.004, 0.0, ground));
  o = over(o, vec3(0.01, 0.0, 0.02), black);
  // the mist, low, creeping
  float mist = fbm(vec2(c.x * 2.5 + t * 0.06, c.y * 4.0 - t * 0.02));
  o = over(o, vec3(0.45, 0.4, 0.55), smoothstep(0.35, 0.8, mist) * smoothstep(0.0, -0.35, c.y) * 0.45);
  // bats, flitting across
  for (int k = 0; k < 5; k++) {
    float fk = float(k);
    float run = fract(t * (0.05 + 0.03 * hash(vec2(fk, 3.0))) + hash(vec2(fk, 4.0)));
    vec2 b = vec2(-1.1 + run * 2.2, 0.1 + 0.35 * hash(vec2(fk, 5.0)) + 0.04 * sin(run * 30.0 + fk));
    vec2 q = (c - b) * (60.0 - 20.0 * hash(vec2(fk, 6.0)));
    float flap = sin(t * 14.0 + fk * 3.0);
    float wing = step(abs(q.x), 2.2) * smoothstep(0.35, 0.0, abs(q.y - abs(q.x) * 0.45 * flap - 0.25 * sin(abs(q.x) * 3.0)));
    float body = smoothstep(0.5, 0.3, length(q * vec2(1.4, 0.9)));
    o = over(o, vec3(0.0), clamp(wing + body, 0.0, 1.0));
  }
  // eyes in the dark, low behind the stones: they open, blink, and are gone
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    vec2 ep = vec2(-0.7 + fk * 0.62 + 0.1 * hash(vec2(fk, 7.0)), -0.27 + 0.03 * hash(vec2(fk, 8.0)));
    float awake = smoothstep(0.55, 0.75, sin(t * (0.21 + 0.05 * fk) + fk * 2.3));
    float lid = step(0.06, fract(t * 0.37 + fk * 0.31));
    float pair = smoothstep(0.007, 0.003, length((c - ep - vec2(-0.016, 0.0)) * vec2(1.0, 2.2))) + smoothstep(0.007, 0.003, length((c - ep - vec2(0.016, 0.0)) * vec2(1.0, 2.2)));
    o = over(o, vec3(1.0, 0.85, 0.2), pair * awake * lid);
    o = over(o, vec3(1.0, 0.7, 0.1), exp(-length(c - ep) * 40.0) * 0.25 * awake * lid);
  }
  // a ghost drifting slowly through the mist
  float gx = mod(t * 0.035, 2.8) - 1.4;
  vec2 gq = (c - vec2(gx, -0.04 + 0.03 * sin(t * 0.8))) * vec2(18.0, 15.0);
  float ghead = smoothstep(1.0, 0.7, length(gq - vec2(0.0, 0.45)));
  float gwide = 0.95 + 0.3 * smoothstep(0.4, -1.4, gq.y);
  float gsheet = smoothstep(0.2, 0.0, abs(gq.x) - gwide) * step(gq.y, 0.45) * smoothstep(-1.6, -1.15, gq.y + 0.22 * sin(gq.x * 6.0 + t * 3.0));
  float ghost = clamp(ghead + gsheet, 0.0, 1.0) * (0.6 + 0.4 * fbm(gq * 0.6 + t * 0.3));
  float geyes = smoothstep(0.17, 0.1, length(gq - vec2(-0.32, 0.55))) + smoothstep(0.17, 0.1, length(gq - vec2(0.32, 0.55)));
  o = over(o, vec3(0.85, 0.9, 1.0), ghost * 0.24);
  o = over(o, vec3(0.05, 0.0, 0.1), geyes * ghost * 0.6);
  // lightning now and then: the sky flares, a bolt forks down behind the hill
  float strike = step(0.965, hash(vec2(floor(t * 4.0), 9.0)));
  float fork = smoothstep(0.006, 0.0, abs(c.x - 0.15 - 0.08 * (noise(vec2(c.y * 14.0, floor(t * 4.0))) - 0.5) - c.y * 0.1)) * step(-0.28, c.y);
  o = over(o, vec3(0.75, 0.72, 1.0), strike * (0.3 * smoothstep(-0.3, 0.5, c.y) + fork));
  o.rgb *= mix(0.35, 1.0, smoothstep(1.1, 0.3, length(c * vec2(0.7, 1.0))));
