// Noël — the booster stage on a winter night: a green aurora rippling far away, snow falling in three layers
  // at their own pace, a garland of coloured lights swinging along the top (a stage: gl_FragCoord, u_res, t).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, mix(vec3(0.01, 0.02, 0.06), vec3(0.03, 0.08, 0.16), smoothstep(-0.6, 0.6, c.y)), 1.0);
  // the aurora: soft curtains, waving
  float curtain = fbm(vec2(c.x * 2.0 + t * 0.05, t * 0.08)) ;
  float band = smoothstep(0.15, 0.0, abs(c.y - 0.28 - 0.12 * sin(c.x * 3.0 + t * 0.2) - 0.1 * curtain));
  o = over(o, mix(vec3(0.1, 0.9, 0.5), vec3(0.3, 0.6, 1.0), smoothstep(-0.5, 0.6, c.x)), band * 0.28 * (0.6 + 0.4 * sin(c.x * 9.0 + t * 0.6)));
  // snow, three layers: the nearer, the bigger and the faster
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    float scale = 20.0 - fk * 6.0;
    vec2 g = c * scale + vec2(0.4 * sin(t * 0.3 + fk), t * (0.6 + fk * 0.35));
    vec2 cell = floor(g);
    vec2 jit = vec2(hash(cell + fk), hash(cell + 4.2 + fk)) - 0.5;
    float flake = step(0.55, hash(cell + 9.0 * fk)) * smoothstep(0.08 + fk * 0.04, 0.0, length(fract(g) - 0.5 - jit * 0.6));
    o = over(o, vec3(0.92, 0.96, 1.0), flake * (0.4 + fk * 0.25));
  }
  // the garland: a swinging wire and its bulbs, each twinkling in its colour
  float sway = 0.01 * sin(t * 0.8);
  float wire = 0.44 - 0.06 * cos(c.x * 3.2) + sway;
  o = over(o, vec3(0.08, 0.12, 0.08), smoothstep(0.004, 0.0, abs(c.y - wire)) * 0.9);
  for (int k = 0; k < 13; k++) {
    float fk = float(k);
    float x = -0.9 + fk * 0.15;
    vec2 b = vec2(x, 0.44 - 0.06 * cos(x * 3.2) + sway - 0.022);
    vec3 col = fk - 4.0 * floor(fk / 4.0) < 0.5 ? vec3(1.0, 0.25, 0.2) : fk - 4.0 * floor(fk / 4.0) < 1.5 ? vec3(1.0, 0.8, 0.25) : fk - 4.0 * floor(fk / 4.0) < 2.5 ? vec3(0.25, 0.9, 0.4) : vec3(0.3, 0.6, 1.0);
    float on = 0.55 + 0.45 * sin(t * 2.3 + fk * 1.7);
    float dd = length((c - b) * vec2(1.0, 0.75));
    o = over(o, col, smoothstep(0.014, 0.008, dd) * (0.5 + 0.5 * on));
    o = over(o, col, exp(-dd * 30.0) * 0.35 * on);
  }
  o.rgb *= mix(0.4, 1.0, smoothstep(1.1, 0.3, length(c * vec2(0.7, 1.0))));
