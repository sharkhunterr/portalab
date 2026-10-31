// Front — the booster stage: a battlefield at dusk, smoke rolling over the trenches, distant flashes lighting the
  // clouds, searchlights sweeping and embers rising (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(mix(vec3(0.12, 0.1, 0.09), vec3(0.42, 0.3, 0.22), smoothstep(-0.3, 0.5, c.y)), 1.0);
  // flashes on the horizon, now here now there
  float ft = floor(t * 1.5), fp = fract(t * 1.5);
  float fx = (hash(vec2(ft, 3.1)) - 0.5) * asp;
  float flash = exp(-fp * 6.0) * step(0.4, hash(vec2(ft, 7.7)));
  o = over(o, vec3(1.0, 0.65, 0.3), flash * exp(-length((c - vec2(fx, -0.18)) * vec2(1.0, 2.5)) * 3.0) * 0.8);
  // searchlights from below
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    vec2 base = vec2((fk - 1.0) * asp * 0.4, -0.6);
    float ang = 0.35 * sin(t * 0.5 + fk * 2.1);
    vec2 d = c - base;
    float along = d.y * cos(ang) + d.x * sin(ang);
    float across = d.x * cos(ang) - d.y * sin(ang);
    float b = smoothstep(0.02 + along * 0.08, 0.0, abs(across)) * step(0.0, along) * smoothstep(1.3, 0.2, along);
    o = over(o, vec3(0.95, 0.95, 0.85), b * 0.22);
  }
  // smoke rolling across
  float sm = fbm(c * vec2(2.0, 3.0) + vec2(t * 0.12, 0.0));
  o = over(o, vec3(0.28, 0.26, 0.24), smoothstep(0.45, 0.8, sm) * 0.7);
  // the trench line, barbed wire posts
  float ground = -0.32 + 0.03 * sin(c.x * 4.0) + 0.015 * sin(c.x * 11.0);
  o = over(o, vec3(0.08, 0.07, 0.05), step(c.y, ground));
  float post = step(abs(fract(c.x * 4.0) - 0.5), 0.012) * step(ground, c.y) * step(c.y, ground + 0.07);
  float wire = step(abs(c.y - ground - 0.05 - 0.012 * sin(c.x * 50.0)), 0.003);
  o = over(o, vec3(0.06, 0.05, 0.04), max(post, wire));
  // embers rising
  vec2 g = c * vec2(14.0, 10.0) + vec2(0.0, -t * 0.8);
  vec2 id = floor(g);
  float em = step(0.93, hash(id)) * smoothstep(0.25, 0.0, length(fract(g) - vec2(0.5 + 0.3 * sin(t + id.x), 0.5)));
  o = over(o, vec3(1.0, 0.55, 0.15), em * 0.9);
  o.rgb *= smoothstep(1.35, 0.35, length(c * vec2(0.8, 1.0)));
