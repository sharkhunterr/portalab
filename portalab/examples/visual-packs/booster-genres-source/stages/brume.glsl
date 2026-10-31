// Brume — the booster stage: a Victorian street lost in fog, gas lamps glowing in it, the fog drifting in slow
  // banks, a silhouette passing now and then (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(mix(vec3(0.03, 0.08, 0.1), vec3(0.09, 0.19, 0.2), smoothstep(-0.5, 0.3, c.y)), 1.0);
  // the houses' roofs and chimneys
  float col = floor((c.x + asp) * 4.0);
  float roof = 0.1 + 0.15 * hash(vec2(col, 1.0)) + 0.04 * step(0.7, fract((c.x + asp) * 4.0)) * step(fract((c.x + asp) * 4.0), 0.8);
  o = over(o, vec3(0.02, 0.05, 0.06), step(c.y, roof) * step(-0.25, c.y));
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    vec2 lp = vec2((fk / 3.0 - 0.5) * asp * 0.85, -0.02);
    o = over(o, vec3(1.0, 0.85, 0.5), exp(-length(c - lp) * 6.0) * 0.55);
    o = over(o, vec3(1.0, 0.9, 0.6), smoothstep(0.018, 0.012, length(c - lp)));
    o = over(o, vec3(0.02, 0.04, 0.05), step(abs(c.x - lp.x), 0.006) * step(c.y, lp.y - 0.02));
  }
  // a figure passing in a cape
  float px = mod(t * 0.12, 1.0) * asp * 1.4 - asp * 0.7;
  vec2 fq = (c - vec2(px, -0.26)) * vec2(1.0, 1.0);
  o = over(o, vec3(0.01, 0.03, 0.04), step(abs(fq.x), 0.025 + max(0.0, -fq.y) * 0.25) * step(-0.0, fq.y + 0.0) * step(fq.y, 0.14) + smoothstep(0.022, 0.018, length(fq - vec2(0.0, 0.16))));
  o = over(o, vec3(0.03, 0.06, 0.07), step(c.y, -0.26));
  float fog = fbm(c * vec2(1.5, 4.0) + vec2(t * 0.05, 0.0)) * fbm(c * 3.0 - vec2(t * 0.03, 0.0) + 4.0);
  o = over(o, vec3(0.62, 0.72, 0.7), smoothstep(0.2, 0.6, fog) * 0.55);
