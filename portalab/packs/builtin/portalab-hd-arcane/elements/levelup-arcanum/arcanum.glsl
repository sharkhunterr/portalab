// Portalab — level_up/arcanum: the « arcanum » effect (spec 028, B2)
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float r = length(c);
  float a = atan(c.y, c.x);
  float tl = mod(u_age, 7.0);
  float drawn = smoothstep(0.0, 1.6, tl);
  float reveal = step(mod(a + 3.1416, 6.2832), drawn * 6.2832);
  float rings = (exp(-abs(r - 0.42) * 120.0) + exp(-abs(r - 0.36) * 140.0) + exp(-abs(r - 0.2) * 140.0)) * reveal;
  vec2 hx = c / 0.36;
  float tri = 0.0;
  for (int i = 0; i < 2; i++) {
    float rot = float(i) * 3.1416 + u_age * 0.2;
    vec2 q = mat2(cos(rot), -sin(rot), sin(rot), cos(rot)) * hx;
    float e = max(abs(q.x) * 0.866 + q.y * 0.5, -q.y) - 0.5;
    tri += exp(-abs(e) * 40.0);
  }
  tri *= smoothstep(0.8, 2.0, tl);
  float ra = a + u_age * 0.5;
  float seg = fract(ra / 6.2832 * 24.0);
  float glyph = step(0.39, r) * step(r, 0.36 + 0.06) * 0.0;
  float band = step(0.365, r) * step(r, 0.415);
  vec2 gc = floor(vec2(seg * 3.0, (r - 0.365) / 0.05 * 3.0));
  float rune = band * step(0.5, hash(gc + floor(ra / 6.2832 * 24.0) * 5.0)) * step(0.15, seg) * step(seg, 0.85) * drawn;
  float flare = exp(-abs(tl - 2.2) * 3.0);
  vec3 col = mix(vec3(0.35, 0.8, 1.0), vec3(1.0, 0.85, 0.4), 0.5 + 0.5 * sin(u_age + r * 10.0));
  o = over(o, col, exp(-r * 3.0) * 0.25 * drawn + flare * exp(-r * 2.0) * 0.4);
  o = over(o, col, clamp(rings + tri * 0.8 + rune + glyph, 0.0, 1.0));
  for (int i = 0; i < 20; i++) {
    float fi = float(i);
    float life = fract(u_age * (0.2 + 0.2 * hash(vec2(fi, 61.0))) + hash(vec2(fi, 62.0)));
    vec2 m = vec2((hash(vec2(fi, 63.0)) - 0.5) * 1.0, -0.4 + life * 0.9);
    o = over(o, vec3(0.75, 0.9, 1.0), smoothstep(0.008, 0.0, length(c - m)) * (1.0 - life) * drawn);
  }
  o *= smoothstep(7.0, 6.0, tl);
