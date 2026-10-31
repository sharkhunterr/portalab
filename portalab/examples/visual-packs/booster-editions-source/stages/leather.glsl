// Cuir & lin — the booster stage: a watercolour sky, soft clouds drifting, hot-air balloons rising slowly, in a
  // rim of stitched leather with brass rivets (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  vec3 sky = mix(vec3(0.84, 0.92, 0.98), vec3(0.5, 0.72, 0.92), smoothstep(-0.5, 0.5, c.y));
  sky += (fbm(c * 3.0 + t * 0.02) - 0.5) * 0.08;
  o = vec4(sky, 1.0);
  float cl = fbm(vec2(c.x * 2.5 - t * 0.03, c.y * 5.0));
  o = over(o, vec3(1.0), smoothstep(0.55, 0.7, cl) * smoothstep(-0.4, 0.1, c.y) * 0.9);
  for (int k = 0; k < 8; k++) {
    float fk = float(k);
    float s = 0.03 + 0.03 * hash(vec2(fk, 1.0));
    vec2 bp = vec2((hash(vec2(fk, 2.0)) - 0.5) * asp * 0.8 + 0.01 * sin(t * 0.7 + fk), fract(hash(vec2(fk, 3.0)) + t * 0.015 * (0.5 + hash(vec2(fk, 4.0)))) * 1.4 - 0.7);
    vec2 q = (c - bp) / s;
    float env = length(vec2(q.x * (1.0 + 0.35 * step(q.y, 0.0) * -q.y), q.y)) - 1.0;
    vec3 col = mod(fk, 4.0) < 1.0 ? vec3(0.92, 0.3, 0.28) : mod(fk, 4.0) < 2.0 ? vec3(0.98, 0.76, 0.25) : mod(fk, 4.0) < 3.0 ? vec3(0.3, 0.6, 0.86) : vec3(0.45, 0.76, 0.4);
    o = over(o, mix(col, vec3(1.0), 0.3 * step(abs(q.x), 0.15)), step(env, 0.0));
    o = over(o, vec3(0.5, 0.32, 0.16), step(abs(q.x), 0.22) * step(abs(q.y + 1.65), 0.15));
  }
  vec2 e = abs(c) - vec2(asp * 0.5 - 0.06, 0.44);
  float rim = max(e.x, e.y);
  o = over(o, vec3(0.45, 0.26, 0.14) * (0.85 + 0.3 * noise(c * 80.0)), step(0.0, rim));
  float st = max(abs(c.x) - (asp * 0.5 - 0.035), abs(c.y) - 0.465);
  float dash = step(0.5, fract((c.x + c.y) * 45.0));
  o = over(o, vec3(0.96, 0.86, 0.62), smoothstep(0.003, 0.0, abs(st)) * dash);
  vec2 rv = abs(c) - vec2(asp * 0.5 - 0.03, 0.47);
  o = over(o, vec3(0.88, 0.7, 0.32), step(length(rv), 0.014));
