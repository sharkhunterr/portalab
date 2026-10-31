// Ténèbres — the booster stage: a misty forest of bare trees under a veiled blood moon, mist creeping, lightning
  // far off now and then (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(mix(vec3(0.02, 0.01, 0.02), vec3(0.12, 0.02, 0.03), smoothstep(0.5, -0.4, c.y)), 1.0);
  vec2 mp = vec2(asp * 0.25, 0.2);
  float md = length(c - mp);
  float strike = pow(max(0.0, sin(t * 0.5) * sin(t * 1.9 + 2.0)), 20.0);
  o = over(o, vec3(0.5, 0.03, 0.05), exp(-md * 4.5) * 0.5);
  o = over(o, mix(vec3(0.85, 0.12, 0.1), vec3(0.45, 0.02, 0.03), smoothstep(0.0, 0.17, md)), smoothstep(0.172, 0.168, md));
  float clouds = fbm(c * vec2(2.0, 5.0) + vec2(t * 0.015, 0.0));
  o = over(o, vec3(0.06, 0.02, 0.03), smoothstep(0.5, 0.75, clouds) * 0.85);
  o = over(o, vec3(0.8, 0.75, 0.9), strike * 0.25);
  // bare trees: a trunk, crooked limbs reaching up and out, twigs at their ends
  float tree = 0.0;
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    vec2 base = vec2((hash(vec2(fk, 3.0)) - 0.5) * asp * 1.1, -0.42);
    float hgt = 0.45 + 0.35 * hash(vec2(fk, 5.0));
    vec2 tip = base + vec2((hash(vec2(fk, 4.0)) - 0.5) * 0.12, hgt);
    vec2 pa = c - base, ba = tip - base;
    float hseg = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    tree = max(tree, smoothstep(0.018 * (1.0 - hseg * 0.8) + 0.002, 0.0, length(pa - ba * hseg)));
    for (int j = 0; j < 5; j++) {
      float fj = float(j);
      float at = 0.35 + 0.13 * fj;
      vec2 from = base + ba * at;
      float side = mod(fj, 2.0) * 2.0 - 1.0;
      float ang = 1.5708 + side * (0.5 + 0.4 * hash(vec2(fk, fj + 10.0)));
      float len = (0.22 - 0.03 * fj) * (0.7 + 0.5 * hash(vec2(fk, fj + 20.0)));
      vec2 to = from + vec2(cos(ang), sin(ang)) * len;
      vec2 pb = c - from, bb = to - from;
      float hb = clamp(dot(pb, bb) / dot(bb, bb), 0.0, 1.0);
      tree = max(tree, smoothstep(0.007 * (1.0 - hb * 0.7) + 0.0015, 0.0, length(pb - bb * hb)));
      vec2 tw = to + vec2(cos(ang + side * 0.6), sin(ang + side * 0.6)) * len * 0.45;
      vec2 pc = c - to, bc = tw - to;
      float hc = clamp(dot(pc, bc) / dot(bc, bc), 0.0, 1.0);
      tree = max(tree, smoothstep(0.0035, 0.0, length(pc - bc * hc)));
    }
  }
  o = over(o, vec3(0.01, 0.005, 0.01), tree);
  o = over(o, vec3(0.01, 0.005, 0.01), step(c.y, -0.38 + 0.03 * sin(c.x * 5.0)));
  float mist = fbm(c * vec2(1.6, 6.0) + vec2(-t * 0.04, 0.0));
  o = over(o, vec3(0.4, 0.3, 0.35), smoothstep(0.45, 0.8, mist) * smoothstep(0.0, -0.45, c.y) * 0.45);
