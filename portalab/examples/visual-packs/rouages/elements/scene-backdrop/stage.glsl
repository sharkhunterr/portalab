// Cogwork — the booster stage in the engine room: a glass roof with an airship drifting past, great gears
  // turning and meshing, a boiler's red glow, jets of steam (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, mix(vec3(0.08, 0.05, 0.03), vec3(0.2, 0.13, 0.08), smoothstep(-0.5, 0.5, c.y)), 1.0);
  // the glass roof and the sky beyond, an airship drifting
  float roof = step(0.25, c.y);
  o = over(o, mix(vec3(0.5, 0.3, 0.3), vec3(0.85, 0.55, 0.3), smoothstep(0.5, 0.25, c.y)), roof * 0.6);
  float bars = step(0.94, fract(c.x * 8.0)) + step(0.92, fract(c.y * 6.0));
  o = over(o, vec3(0.15, 0.1, 0.06), clamp(bars, 0.0, 1.0) * roof);
  vec2 ship = c - vec2(mod(t * 0.02, 2.4) - 1.2, 0.38);
  o = over(o, vec3(0.35, 0.18, 0.1), smoothstep(0.004, 0.0, length(ship * vec2(1.0, 3.2)) - 0.09) * roof);
  // the boiler's glow
  o = over(o, vec3(1.0, 0.35, 0.1), exp(-length((c - vec2(0.0, -0.5)) * vec2(0.8, 1.6)) * 3.0) * (0.35 + 0.1 * sin(t * 3.0)));
  // the gears
  for (int k = 0; k < 5; k++) {
    float fk = float(k);
    vec2 centre = vec2(-0.75 + fk * 0.38, fk < 0.5 || fk > 3.5 ? -0.05 : -0.3 + 0.2 * mod(fk, 2.0));
    float rad = 0.12 + 0.06 * hash(vec2(fk, 1.0));
    vec2 q = c - centre;
    float a = atan(q.y, q.x) + (mod(fk, 2.0) < 0.5 ? 1.0 : -1.0) * t * 0.3 / rad * 0.1;
    float r = length(q);
    float gear = smoothstep(0.004, 0.0, r - rad - 0.02 * step(0.0, sin(a * rad * 100.0))) - smoothstep(0.004, 0.0, r - rad * 0.8);
    gear += smoothstep(0.01, 0.0, abs(sin(a * 3.0)) * r) * step(r, rad * 0.8) + smoothstep(0.004, 0.0, r - rad * 0.18);
    o = over(o, mix(vec3(0.45, 0.3, 0.1), vec3(0.85, 0.62, 0.28), 0.5 + 0.5 * sin(a * 2.0 + fk)), clamp(gear, 0.0, 1.0) * 0.9);
  }
  // jets of steam
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    vec2 base = vec2(-0.5 + fk * 0.5, -0.45);
    vec2 q = c - base;
    float on = step(0.4, fract(t * 0.2 + fk * 0.33));
    float jet = fbm(vec2(q.x * 7.0, q.y * 4.0 - t * 3.0)) * smoothstep(0.05 + q.y * 0.3, 0.0, abs(q.x)) * step(0.0, q.y) * smoothstep(0.6, 0.1, q.y);
    o = over(o, vec3(0.9, 0.88, 0.84), jet * on * 0.7);
  }
  o.rgb *= mix(0.4, 1.0, smoothstep(1.1, 0.3, length(c * vec2(0.7, 1.0))));
