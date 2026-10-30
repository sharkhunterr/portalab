// Mecha — the booster stage: a dark hangar — a grid of cyan neon running to the horizon, searchlights sweeping,
  // interface hexagons pulsing, sparks falling, warning lights blinking (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(mix(vec3(0.02, 0.03, 0.06), vec3(0.04, 0.08, 0.12), smoothstep(0.5, -0.2, c.y)), 1.0);
  // the floor's grid, in perspective, running towards the viewer
  float horizon = -0.12;
  if (c.y < horizon) {
    float depth = 0.12 / (horizon - c.y + 0.001);
    vec2 g = vec2(c.x * depth * 2.0, depth + t * 0.6);
    vec2 cell = abs(fract(g) - 0.5);
    float line = smoothstep(0.44, 0.5, max(cell.x, cell.y));
    o = over(o, vec3(0.15, 0.85, 1.0), line * smoothstep(0.0, 0.3, horizon - c.y) * 0.6);
  }
  o = over(o, vec3(0.2, 0.9, 1.0), exp(-abs(c.y - horizon) * 60.0) * 0.4);
  // the hangar's back wall: hexagons pulsing
  vec2 h = c * 9.0;
  vec2 hr = vec2(1.0, 1.732);
  vec2 ha = mod(h, hr) - hr * 0.5;
  vec2 hb = mod(h - hr * 0.5, hr) - hr * 0.5;
  vec2 hg = dot(ha, ha) < dot(hb, hb) ? ha : hb;
  vec2 hid = h - hg;
  float hexd = max(dot(abs(hg), vec2(0.5, 0.866)), abs(hg.x));
  float pulse = pow(0.5 + 0.5 * sin(t * 1.3 - hid.x * 0.4 + hash(hid) * 6.0), 6.0);
  o = over(o, vec3(0.2, 0.8, 1.0), smoothstep(0.03, 0.0, abs(hexd - 0.46)) * step(horizon, c.y) * (0.08 + 0.3 * pulse));
  // searchlights sweeping
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    vec2 src = vec2((fk - 0.5) * asp * 0.9, -0.5);
    float ang = 1.5708 + 0.45 * sin(t * (0.3 + fk * 0.11) + fk * 2.0);
    vec2 dir = vec2(cos(ang), sin(ang));
    vec2 rel = c - src;
    float along = dot(rel, dir);
    float across = abs(rel.x * dir.y - rel.y * dir.x);
    o = over(o, vec3(0.6, 0.95, 1.0), smoothstep(0.03 + along * 0.18, 0.0, across) * step(0.0, along) * exp(-along * 1.2) * 0.22);
  }
  // warning lights blinking along the walls
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    vec2 lp = vec2((fk / 5.0 - 0.5) * asp * 0.9, 0.42);
    float on = step(0.5, fract(t * 0.8 + fk * 0.37));
    o = over(o, vec3(1.0, 0.55, 0.1), exp(-length(c - lp) * 60.0) * on * 0.9);
  }
  // sparks falling
  for (int k = 0; k < 14; k++) {
    float fk = float(k);
    float h1 = hash(vec2(fk, 1.0));
    float age = fract(t * (0.3 + 0.3 * h1) + h1);
    vec2 sp = vec2((h1 - 0.5) * asp + age * 0.08, 0.45 - age * age * 0.9);
    o = over(o, vec3(1.0, 0.8, 0.3), exp(-length(c - sp) * 500.0) * (1.0 - age));
  }
