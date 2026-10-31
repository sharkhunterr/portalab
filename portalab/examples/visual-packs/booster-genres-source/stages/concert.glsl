// Concert — the booster stage: a stage in the smoke, beams of coloured light sweeping, the crowd's raised hands
  // in silhouette, an equaliser glowing at the back (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(mix(vec3(0.04, 0.02, 0.07), vec3(0.14, 0.06, 0.22), smoothstep(-0.5, 0.5, c.y)), 1.0);
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    vec2 src = vec2((fk / 5.0 - 0.5) * asp * 0.8, 0.5);
    float ang = -1.5708 + 0.5 * sin(t * (0.35 + fk * 0.05) + fk * 1.7);
    vec2 dir = vec2(cos(ang), sin(ang));
    vec2 rel = c - src;
    float along = dot(rel, dir);
    float across = abs(rel.x * dir.y - rel.y * dir.x);
    vec3 col = mod(fk, 3.0) < 1.0 ? vec3(1.0, 0.18, 0.66) : mod(fk, 3.0) < 2.0 ? vec3(0.16, 0.89, 1.0) : vec3(0.48, 0.17, 1.0);
    o = over(o, col, smoothstep(0.02 + along * 0.12, 0.0, across) * step(0.0, along) * 0.35);
  }
  float smoke = fbm(c * 2.0 + vec2(t * 0.04, t * 0.02));
  o = over(o, vec3(0.5, 0.35, 0.6), smoothstep(0.5, 0.8, smoke) * 0.25);
  // the equaliser at the back of the stage
  float bx = floor((c.x + asp) * 30.0);
  float bh = 0.08 + 0.12 * abs(sin(t * 3.0 + bx * 0.7) * sin(t * 1.3 + bx * 0.3));
  o = over(o, vec3(0.16, 0.89, 1.0), step(c.y, -0.05 + bh) * step(-0.05, c.y) * step(0.2, fract((c.x + asp) * 30.0)) * 0.6);
  // the crowd
  float hx = (c.x + asp) * 14.0;
  float head = smoothstep(0.032, 0.026, length(vec2((fract(hx) - 0.5) / 14.0, c.y + 0.4 + 0.008 * sin(floor(hx) * 2.0 + t * 3.0))));
  float body = step(c.y, -0.43);
  float hand = step(abs(fract(hx + 0.3) - 0.5), 0.06) * step(c.y, -0.28 + 0.04 * sin(t * 4.0 + floor(hx))) * step(-0.43, c.y) * step(0.5, hash(vec2(floor(hx), 2.0)));
  o = over(o, vec3(0.01, 0.0, 0.02), max(max(head, body), hand));
