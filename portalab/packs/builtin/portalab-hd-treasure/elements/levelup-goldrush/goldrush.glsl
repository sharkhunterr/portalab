// Portalab — level_up/goldrush: the « goldrush » effect (spec 028, B2)
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float aspect = u_res.x / u_res.y;
  float glow = exp(-length(c) * 2.5) * smoothstep(0.0, 0.6, tl) * smoothstep(7.0, 5.5, tl);
  float rays = pow(max(0.0, sin(atan(c.y, c.x) * 12.0 + u_age * 0.5)), 6.0) * glow;
  o = over(o, vec3(1.0, 0.78, 0.3), glow * 0.35 + rays * 0.35);
  for (int i = 0; i < 30; i++) {
    float fi = float(i);
    float start = 0.0;
    float life = fract(u_age * (0.22 + 0.15 * hash(vec2(fi, 81.0))) + hash(vec2(fi, 84.0)));
    vec2 pos = vec2((hash(vec2(fi, 82.0)) - 0.5) * aspect + sin(life * 5.0 + fi) * 0.03, 0.62 - life * 1.3);
    float spin = abs(cos(u_age * (2.0 + hash(vec2(fi, 83.0)) * 3.0) + fi));
    vec2 q = (c - pos) / vec2(0.028 * max(spin, 0.12), 0.028);
    float coin = smoothstep(1.0, 0.85, length(q)) * step(start, tl);
    float rim = smoothstep(0.75, 0.95, length(q)) * coin;
    vec3 cc = mix(vec3(0.75, 0.5, 0.1), vec3(1.0, 0.85, 0.35), spin) + vec3(1.0) * smoothstep(0.3, 0.0, length(q - vec2(-0.35, 0.35))) * 0.6;
    o = over(o, mix(cc, vec3(0.55, 0.35, 0.05), rim * 0.6), coin);
  }
  vec2 sg = c * 25.0;
  o = over(o, vec3(1.0, 0.95, 0.7), step(0.985, hash(floor(sg) + floor(u_age * 4.0))) * smoothstep(0.4, 0.0, length(fract(sg) - 0.5)) * glow * 3.0);
