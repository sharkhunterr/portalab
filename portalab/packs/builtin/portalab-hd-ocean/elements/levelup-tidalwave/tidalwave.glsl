// Portalab — level_up/tidalwave: the « tidalwave » effect (spec 028, B2)
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float tt = u_age;
  float aspect = u_res.x / u_res.y;
  float level = smoothstep(0.0, 1.4, tl) * 0.38 * smoothstep(6.5, 5.0, tl);
  float crestX = -aspect * 0.6 + (tl - 0.6) * aspect * 0.45;
  float bump = 0.32 * exp(-pow((c.x - crestX) * 2.4, 2.0)) * smoothstep(0.4, 1.2, tl) * smoothstep(6.0, 4.0, tl);
  float surf = level + bump + 0.025 * sin(c.x * 10.0 - tt * 3.0) + 0.015 * sin(c.x * 23.0 + tt * 4.0);
  float depth = clamp((surf - uv.y) * 3.0, 0.0, 1.0);
  vec3 water = mix(vec3(0.25, 0.75, 0.9), vec3(0.02, 0.15, 0.35), depth);
  float caustic = 1.0 - abs(2.0 * fbm(c * 6.0 + vec2(tt * 0.5, tt * 0.3)) - 1.0);
  water += vec3(0.6, 0.95, 1.0) * smoothstep(0.9, 0.99, caustic) * (1.0 - depth) * 0.6;
  o = over(o, water, step(uv.y, surf) * 0.88);
  float foam = smoothstep(0.03, 0.0, abs(uv.y - surf)) * (0.6 + 0.4 * noise(vec2(c.x * 30.0, tt * 3.0)));
  foam += smoothstep(0.08, 0.0, abs(uv.y - surf)) * exp(-pow((c.x - crestX) * 4.0, 2.0)) * fbm(c * 20.0 + tt);
  o = over(o, vec3(0.95, 1.0, 1.0), clamp(foam, 0.0, 1.0) * 0.9);
  for (int i = 0; i < 24; i++) {
    float fi = float(i);
    float life = fract(tt * (0.6 + 0.4 * hash(vec2(fi, 51.0))) + hash(vec2(fi, 52.0)));
    vec2 sp = vec2(crestX + (hash(vec2(fi, 53.0)) - 0.3) * 0.3 + life * 0.25, level + bump - 0.5 + life * 0.25 - life * life * 0.3);
    o = over(o, vec3(0.9, 0.97, 1.0), smoothstep(0.01, 0.0, length(c - sp)) * (1.0 - life) * smoothstep(0.4, 1.2, tl));
  }
