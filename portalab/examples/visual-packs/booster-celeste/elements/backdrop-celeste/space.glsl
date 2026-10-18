// Céleste — the booster stage in deep space: nebulae drifting in two colours, a field of twinkling stars, a
  // ringed planet low on the left, a shooting star now and then (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, mix(vec3(0.01, 0.0, 0.04), vec3(0.03, 0.02, 0.1), smoothstep(-0.6, 0.6, c.y)), 1.0);
  // the nebulae: two folded clouds, slowly drifting
  vec2 q = c * 2.2 + vec2(t * 0.012, -t * 0.008);
  float w = fbm(q + fbm(q * 1.7 + t * 0.02));
  float neb = smoothstep(0.42, 0.85, w);
  o = over(o, mix(vec3(0.45, 0.12, 0.6), vec3(0.1, 0.55, 0.65), smoothstep(-0.4, 0.5, c.x + 0.3 * c.y)), neb * 0.55);
  o = over(o, vec3(1.0, 0.45, 0.7), smoothstep(0.7, 0.95, w) * 0.25);
  // the stars: one in a few cells, each its own size, twinkling at its own pace
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    vec2 g = c * (34.0 + fk * 26.0) + fk * 7.3;
    vec2 cell = floor(g);
    vec2 jit = vec2(hash(cell + 1.7), hash(cell + 9.1)) - 0.5;
    float star = step(0.93 - fk * 0.03, hash(cell)) * smoothstep(0.12, 0.0, length(fract(g) - 0.5 - jit * 0.7));
    float tw = 0.55 + 0.45 * sin(t * (1.0 + 2.0 * hash(cell + 3.3)) + hash(cell) * 40.0);
    o = over(o, mix(vec3(0.75, 0.85, 1.0), vec3(1.0, 0.9, 0.75), hash(cell + 5.5)), star * tw);
  }
  // the ringed planet, lit from the right
  vec2 pc = c - vec2(-0.62, -0.28);
  float pr = 0.17;
  float body = smoothstep(pr, pr - 0.004, length(pc));
  float light = clamp(dot(normalize(vec3(pc, sqrt(max(pr * pr - dot(pc, pc), 0.0)))), normalize(vec3(0.8, 0.4, 0.5))), 0.0, 1.0);
  float bands = 0.5 + 0.5 * sin(pc.y * 70.0 + fbm(pc * 9.0) * 4.0);
  vec3 globe = mix(vec3(0.55, 0.32, 0.2), vec3(0.95, 0.75, 0.5), bands) * (0.12 + 0.95 * light);
  vec2 rc = vec2(pc.x * 0.97 + pc.y * 0.24, (pc.y * 0.97 - pc.x * 0.24) * 3.4);
  float ring = smoothstep(0.012, 0.0, abs(length(rc) - 0.27)) + 0.6 * smoothstep(0.02, 0.0, abs(length(rc) - 0.235));
  float front = step(0.0, -rc.y) + (1.0 - body);
  o = over(o, globe, body);
  o = over(o, vec3(0.95, 0.85, 0.7), clamp(ring, 0.0, 1.0) * 0.75 * clamp(front, 0.0, 1.0));
  // a shooting star every few seconds, crossing the sky
  float run = fract(t * 0.09);
  vec2 head = vec2(0.9 - run * 2.4, 0.42 - run * 0.5);
  vec2 dir = normalize(vec2(-2.4, -0.5));
  vec2 rel = c - head;
  float along = dot(rel, -dir);
  float across = abs(dot(rel, vec2(-dir.y, dir.x)));
  float trail = smoothstep(0.0025, 0.0, across) * smoothstep(0.3, 0.0, along) * step(0.0, along);
  o = over(o, vec3(0.9, 0.95, 1.0), (trail * 0.8 + smoothstep(0.012, 0.0, length(rel))) * smoothstep(0.0, 0.08, run) * smoothstep(0.55, 0.4, run));
  // the far edges into black
  o.rgb *= mix(0.35, 1.0, smoothstep(1.1, 0.3, length(c * vec2(0.7, 1.0))));
