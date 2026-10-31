// Arcanes — the booster stage: a night sky crossed by teal and violet auroras, floating islands in silhouette,
  // a moon, stars and gold dust rising (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(mix(vec3(0.02, 0.02, 0.08), vec3(0.08, 0.05, 0.2), smoothstep(-0.5, 0.5, c.y)), 1.0);
  for (int k = 0; k < 40; k++) {
    float fk = float(k);
    vec2 sp = vec2((hash(vec2(fk, 7.0)) - 0.5) * asp, (hash(vec2(fk, 8.0)) - 0.5));
    float tw = 0.5 + 0.5 * sin(t * (1.0 + 2.0 * hash(vec2(fk, 9.0))) + fk);
    o = over(o, vec3(1.0), exp(-length(c - sp) * 700.0) * tw);
  }
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float y = 0.15 + 0.1 * fk + 0.06 * sin(c.x * 3.0 + t * 0.2 + fk * 2.0) + 0.03 * sin(c.x * 7.0 - t * 0.3);
    float band = exp(-abs(c.y - y) * 18.0) * (0.6 + 0.4 * sin(c.x * 20.0 + t * 0.5 + fk));
    o = over(o, mix(vec3(0.2, 0.95, 0.85), vec3(0.6, 0.35, 1.0), fk), band * 0.7);
  }
  vec2 mp = vec2(-asp * 0.3, 0.3);
  o = over(o, vec3(0.95, 0.95, 1.0), smoothstep(0.062, 0.058, length(c - mp)));
  o = over(o, vec3(0.6, 0.6, 1.0), exp(-length(c - mp) * 10.0) * 0.3);
  // floating islands: a jagged rock hanging under a flat grassy top, a crystal glowing on it
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    vec2 ip = vec2((fk / 3.0 - 0.5) * asp * 0.8, -0.12 + 0.18 * hash(vec2(fk, 2.0)) + 0.012 * sin(t * 0.5 + fk));
    float w = 0.07 + 0.06 * hash(vec2(fk, 3.0));
    vec2 q = c - ip;
    float jag = 0.012 * sin(q.x * 90.0 + fk) + 0.008 * sin(q.x * 37.0);
    float rock = step(q.y, 0.0) * step(abs(q.x), w * (1.0 + (q.y + jag) / (w * 1.5)));
    float grass = step(-0.004, q.y) * step(q.y, 0.012 + 0.004 * sin(q.x * 120.0)) * step(abs(q.x), w);
    o = over(o, vec3(0.04, 0.03, 0.09), rock);
    o = over(o, vec3(0.08, 0.2, 0.18), grass);
    vec2 cp = q - vec2(w * 0.3, 0.03);
    o = over(o, vec3(0.3, 1.0, 0.9), smoothstep(0.012, 0.0, abs(cp.x) * 2.0 + abs(cp.y)) + exp(-length(cp) * 60.0) * 0.35);
  }
  for (int k = 0; k < 20; k++) {
    float fk = float(k);
    float h1 = hash(vec2(fk, 1.0));
    vec2 sp = vec2((h1 - 0.5) * asp + 0.04 * sin(t * 0.5 + fk), fract(hash(vec2(fk, 2.0)) + t * 0.02) * 1.2 - 0.6);
    o = over(o, vec3(1.0, 0.85, 0.45), exp(-length(c - sp) * 500.0));
  }
