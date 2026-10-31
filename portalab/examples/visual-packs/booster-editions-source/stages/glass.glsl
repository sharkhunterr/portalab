// Verre liquide — the booster stage: an aurora's veils moving under plates of frosted glass, each with its light
  // on top and its bright edge, a glint crossing them (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(0.015, 0.025, 0.08, 1.0);
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    float y = 0.28 - fk * 0.17 + 0.07 * sin(c.x * 3.0 + t * 0.4 + fk * 1.7) + 0.03 * sin(c.x * 7.0 - t * 0.3);
    float veil = exp(-abs(c.y - y) * 9.0) * (0.6 + 0.4 * fbm(vec2(c.x * 4.0 + t * 0.1, fk)));
    vec3 col = k == 0 ? vec3(0.25, 1.0, 0.65) : k == 1 ? vec3(0.15, 0.75, 0.95) : k == 2 ? vec3(0.6, 0.4, 1.0) : vec3(1.0, 0.45, 0.8);
    o.rgb += col * veil * 0.55;
  }
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    vec2 pp = vec2((hash(vec2(fk, 1.0)) - 0.5) * asp * 0.9 + 0.03 * sin(t * 0.3 + fk), (hash(vec2(fk, 2.0)) - 0.5) * 0.8 + 0.02 * cos(t * 0.25 + fk));
    vec2 sz = vec2(0.1 + 0.08 * hash(vec2(fk, 3.0)), 0.07 + 0.06 * hash(vec2(fk, 4.0)));
    vec2 q = abs(c - pp) - sz + 0.03;
    float sd = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - 0.03;
    float inside = step(sd, 0.0);
    o.rgb = mix(o.rgb, mix(o.rgb, vec3(0.86, 0.93, 1.0), 0.18) * 1.15, inside);
    o = over(o, vec3(1.0), smoothstep(0.003, 0.0, abs(sd)) * (0.3 + 0.5 * step(0.0, c.y - pp.y)));
    o = over(o, vec3(1.0), inside * smoothstep(0.012, 0.0, abs(c.y - pp.y - sz.y + 0.012)) * step(abs(c.x - pp.x), sz.x - 0.04) * 0.6);
  }
  float gx = fract(t / 5.0) * (asp + 1.2) - asp * 0.5 - 0.6;
  o = over(o, vec3(1.0), exp(-abs((c.x - gx) + c.y * 0.6) * 50.0) * 0.18);
