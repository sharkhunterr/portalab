// Néon 2077 — the booster stage in a megacity at night: towers in two depths with lit windows, holographic ads
  // crackling on them, flying cars streaking between, rain falling, a wet street mirroring the neon below, and
  // now and then a band of glitch tearing across (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  // glitch: a band shifted sideways now and then
  float gwin = floor(t * 3.0);
  float glitch = step(0.9, hash(vec2(gwin, 1.0)));
  float gband = step(abs(c.y - (hash(vec2(gwin, 2.0)) - 0.5) * 0.8), 0.03 + 0.04 * hash(vec2(gwin, 3.0)));
  c.x += glitch * gband * (hash(vec2(gwin, 4.0)) - 0.5) * 0.1;
  float ground = -0.28;
  // the street mirrors what is above it, rippled
  vec2 s = c;
  float wet = step(c.y, ground);
  if (wet > 0.5) { s.y = 2.0 * ground - c.y; s.x += 0.006 * sin(c.y * 120.0 + t * 3.0); }
  o = over(o, mix(vec3(0.03, 0.0, 0.06), vec3(0.18, 0.03, 0.2), smoothstep(-0.2, 0.6, s.y)), 1.0);
  // towers: far ones, then near ones, their lit windows flickering
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float w = 0.09 - fk * 0.02;
    float col = floor((s.x + fk * 0.37) / w);
    float h = ground + 0.25 + 0.45 * hash(vec2(col, 5.0 + fk)) - fk * 0.12;
    float tower = step(s.y, h) * step(0.08, fract((s.x + fk * 0.37) / w));
    vec3 body = mix(vec3(0.05, 0.03, 0.1), vec3(0.02, 0.01, 0.04), fk);
    o = over(o, body, tower);
    vec2 win = vec2(fract((s.x + fk * 0.37) / w) * 6.0, (s.y - ground) * 70.0);
    float lit = step(0.6, hash(floor(win) + col * 13.0 + fk)) * step(0.25, fract(win.x)) * step(0.3, fract(win.y)) * tower;
    float flick = step(0.04, fract(t * 0.3 + hash(floor(win) + col)));
    o = over(o, mix(vec3(1.0, 0.75, 0.3), vec3(0.4, 0.9, 1.0), step(0.5, hash(floor(win) + col * 7.0))), lit * flick * (0.5 - fk * 0.15));
  }
  // holograms on the towers: a pink and a cyan panel, crackling, scanlined
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    vec2 hp = vec2(-0.7 + fk * 0.62, 0.05 + 0.18 * hash(vec2(fk, 9.0)));
    vec2 hq = s - hp;
    float panel = step(abs(hq.x), 0.08) * step(abs(hq.y), 0.05);
    float crackle = step(0.08, fract(t * (0.7 + fk * 0.3))) * (0.75 + 0.25 * step(0.5, fract(hq.y * 120.0)));
    vec3 tint = fk < 0.5 ? vec3(1.0, 0.2, 0.7) : fk < 1.5 ? vec3(0.2, 0.95, 1.0) : vec3(0.99, 0.93, 0.04);
    o = over(o, tint, panel * crackle * 0.55);
    o = over(o, tint, exp(-length(hq * vec2(0.6, 1.0)) * 12.0) * 0.25 * crackle);
  }
  // flying cars streaking across between the towers, their light trails
  for (int k = 0; k < 5; k++) {
    float fk = float(k);
    float dir = mod(fk, 2.0) < 0.5 ? 1.0 : -1.0;
    float run = fract(t * (0.08 + 0.05 * hash(vec2(fk, 1.0))) + hash(vec2(fk, 2.0)));
    vec2 cp = vec2(dir * (-1.1 + run * 2.2), 0.0 + 0.32 * hash(vec2(fk, 3.0)));
    vec2 q = s - cp;
    float trail = smoothstep(0.003, 0.0, abs(q.y)) * smoothstep(0.25, 0.0, -q.x * dir) * step(0.0, -q.x * dir);
    o = over(o, mix(vec3(1.0, 0.2, 0.3), vec3(1.0, 0.95, 0.85), step(0.5, hash(vec2(fk, 4.0)))), trail * 0.8);
    o = over(o, vec3(1.0, 0.9, 0.8), exp(-length(q) * 200.0));
  }
  // the street itself: dark and wet, the mirror dimmed
  o.rgb *= mix(1.0, 0.45, wet);
  o = over(o, vec3(0.99, 0.93, 0.04), smoothstep(0.003, 0.0, abs(c.y - ground)) * 0.5);
  // rain
  vec2 rg = vec2(c.x * 70.0 + c.y * 8.0, c.y * 10.0 + t * 14.0);
  float drop = step(0.92, hash(vec2(floor(rg.x), floor(rg.y)))) * smoothstep(0.1, 0.0, abs(fract(rg.x) - 0.5));
  o = over(o, vec3(0.7, 0.8, 1.0), drop * 0.35);
  // the glitch band, its colours split
  o = over(o, vec3(0.2, 1.0, 1.0), glitch * gband * 0.15);
  o.rgb *= mix(0.4, 1.0, smoothstep(1.1, 0.3, length(c * vec2(0.7, 1.0))));
