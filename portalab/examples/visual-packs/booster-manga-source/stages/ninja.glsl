// Ninja — the booster stage: night, a huge red moon veiled by drifting clouds, silhouettes of tiled roofs, mist,
  // maple leaves falling and, now and then, a ninja's shadow leaping across the moon (a stage: gl_FragCoord,
  // u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(mix(vec3(0.03, 0.04, 0.09), vec3(0.1, 0.06, 0.12), smoothstep(0.5, -0.4, c.y)), 1.0);
  // the moon, its glow, clouds crossing it
  vec2 mp = vec2(asp * 0.22, 0.17);
  float md = length(c - mp);
  o = over(o, vec3(0.6, 0.1, 0.08), exp(-md * 5.0) * 0.45);
  o = over(o, mix(vec3(0.95, 0.35, 0.18), vec3(0.62, 0.08, 0.05), smoothstep(0.0, 0.26, md)), smoothstep(0.255, 0.25, md));
  float clouds = fbm(c * vec2(2.0, 6.0) + vec2(t * 0.02, 0.0));
  o = over(o, vec3(0.08, 0.05, 0.1), smoothstep(0.55, 0.75, clouds) * 0.75);
  // a ninja's shadow leaping across the moon now and then
  float cycle = mod(t, 11.0);
  vec2 np = mp + vec2(-0.4 + cycle * 0.35, 0.12 - 0.5 * pow(cycle * 0.35 - 0.4, 2.0));
  vec2 nd = (c - np) * 30.0;
  float ninja = smoothstep(1.0, 0.8, length(nd * vec2(1.0, 0.6))) + smoothstep(0.6, 0.4, length(nd - vec2(0.9, 0.5)));
  o = over(o, vec3(0.02, 0.01, 0.03), clamp(ninja, 0.0, 1.0) * step(cycle, 2.4));
  // tiled roofs: three pagodas and the town's eaves along the foot, in silhouette — each roof sweeping up at its
  // ends
  float town = -0.36 + 0.03 * step(0.5, fract(c.x * 2.3)) + 0.02 * pow(abs(fract(c.x * 4.6) - 0.5) * 2.0, 4.0);
  float shape = step(c.y, town);
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    float px = (fk - 1.0) * asp * 0.36 + 0.05;
    float dx = abs(c.x - px);
    for (int j = 0; j < 4; j++) {
      float fj = float(j);
      float base = -0.36 + fj * 0.07 + 0.02 * fk;
      float w = 0.13 - fj * 0.025;
      float eave = base + 0.035 + 0.025 * pow(dx / w, 3.0) - 0.012 * (1.0 - dx / w);
      shape = max(shape, step(dx, w) * step(base, c.y) * step(c.y, eave));
      shape = max(shape, step(dx, w * 0.55) * step(base - 0.04, c.y) * step(c.y, base));
    }
    shape = max(shape, step(dx, 0.004) * step(c.y, -0.36 + 0.33 + 0.02 * fk));
  }
  o = over(o, vec3(0.02, 0.02, 0.05), shape);
  // mist
  o = over(o, vec3(0.35, 0.3, 0.45), smoothstep(0.5, 0.85, fbm(c * vec2(2.0, 5.0) + vec2(-t * 0.03, 0.0))) * smoothstep(0.0, -0.4, c.y) * 0.3);
  // maple leaves falling
  for (int k = 0; k < 16; k++) {
    float fk = float(k);
    float h1 = hash(vec2(fk, 1.0));
    vec2 lp = vec2((h1 - 0.5) * asp + 0.08 * sin(t * 0.7 + fk), 0.65 - fract(hash(vec2(fk, 2.0)) + t * (0.03 + 0.03 * h1)) * 1.3);
    vec2 ld = c - lp;
    float a = t * (1.0 + h1) + fk;
    ld = vec2(ld.x * cos(a) - ld.y * sin(a), ld.x * sin(a) + ld.y * cos(a));
    float leaf = smoothstep(0.012, 0.009, length(ld * vec2(1.0, 1.8)));
    o = over(o, mix(vec3(0.85, 0.2, 0.08), vec3(1.0, 0.5, 0.15), hash(vec2(fk, 4.0))), leaf);
  }
