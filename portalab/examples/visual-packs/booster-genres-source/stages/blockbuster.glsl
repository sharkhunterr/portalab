// Blockbuster — the booster stage: a city at night in silhouette, searchlights sweeping a smoky sky, an orange
  // glow on the horizon, embers rising (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(mix(vec3(0.03, 0.04, 0.07), vec3(0.18, 0.08, 0.04), smoothstep(0.4, -0.3, c.y)), 1.0);
  float smoke = fbm(c * vec2(1.5, 2.5) + vec2(t * 0.03, 0.0));
  o = over(o, vec3(0.28, 0.22, 0.24), smoothstep(0.45, 0.8, smoke) * 0.45);
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    vec2 src = vec2((fk - 1.0) * asp * 0.4, -0.5);
    float ang = 1.5708 + 0.5 * sin(t * (0.25 + fk * 0.07) + fk * 2.1);
    vec2 dir = vec2(cos(ang), sin(ang));
    vec2 rel = c - src;
    float along = dot(rel, dir);
    float across = abs(rel.x * dir.y - rel.y * dir.x);
    o = over(o, vec3(0.75, 0.82, 1.0), smoothstep(0.02 + along * 0.12, 0.0, across) * step(0.0, along) * exp(-along * 0.9) * 0.3);
  }
  o = over(o, vec3(1.0, 0.45, 0.1), exp(-abs(c.y + 0.22) * 9.0) * 0.45);
  // the skyline: towers of random heights, lit windows
  float col = floor((c.x + asp) * 14.0);
  float h = -0.2 + 0.28 * hash(vec2(col, 1.0)) + 0.1 * step(0.85, hash(vec2(col, 2.0)));
  float town = step(c.y, h);
  o = over(o, vec3(0.02, 0.025, 0.04), town);
  vec2 win = fract(vec2((c.x + asp) * 14.0 * 4.0, c.y * 60.0));
  float lit = step(0.7, hash(floor(vec2((c.x + asp) * 56.0, c.y * 60.0)))) * step(0.3, win.x) * step(win.x, 0.7) * step(0.3, win.y) * step(win.y, 0.7);
  o = over(o, vec3(1.0, 0.75, 0.35), town * lit * step(c.y, h - 0.02) * 0.7);
  for (int k = 0; k < 18; k++) {
    float fk = float(k);
    float h1 = hash(vec2(fk, 1.0));
    float age = fract(t * (0.08 + 0.08 * h1) + h1);
    vec2 sp = vec2((h1 - 0.5) * asp + 0.05 * sin(t + fk), -0.4 + age * 1.0);
    o = over(o, vec3(1.0, 0.6, 0.2), exp(-length(c - sp) * 400.0) * (1.0 - age));
  }
