// Portalab — title/runes: the « runes » effect (spec 028, B2)
  float ang = atan(p.y, p.x / ax) + t * 0.4;
  float id = floor(ang / 6.2831 * 12.0);
  float u = fract(ang / 6.2831 * 12.0);
  float band = (d - 0.1) / 0.28;
  vec2 lc = vec2(u, band) * 3.0;
  vec2 gc = floor(lc);
  vec2 gf = fract(lc);
  float stroke = step(0.45, hash(gc + id * 7.0)) * smoothstep(0.22, 0.0, abs(gf.x - 0.5))
               + step(0.6, hash(gc + id * 3.0)) * smoothstep(0.22, 0.0, abs(gf.y - 0.5));
  float rune = clamp(stroke, 0.0, 1.0) * step(0.0, band) * step(band, 1.0) * step(0.15, u) * step(u, 0.85);
  float pulse = 0.6 + 0.4 * sin(t * 2.0 + id);
  o = over(o, vec3(0.35, 0.75, 1.0), exp(-abs(d - 0.24) * 8.0) * 0.25 * step(0.0, d));
  o = over(o, vec3(0.65, 0.9, 1.0), rune * pulse);
  vec2 sw = p + vec2(fbm(p * 1.5 + t * 0.2), fbm(p * 1.5 - t * 0.15)) * 0.8;
  vec3 body = mix(vec3(0.05, 0.03, 0.18), vec3(0.28, 0.15, 0.62), fbm(sw * 2.0));
  body += vec3(1.0, 0.8, 0.35) * smoothstep(-0.12, 0.0, d) * 0.55;
  for (int i = 0; i < 6; i++) {
    float fi = float(i);
    float life = fract(t * (0.3 + 0.2 * hash(vec2(fi, 21.0))) + hash(vec2(fi, 22.0)));
    vec2 m = vec2((hash(vec2(fi, 23.0)) - 0.5) * 1.6 * ax, -0.9 + life * 1.8);
    body += vec3(0.7, 0.9, 1.0) * smoothstep(0.08, 0.0, length(p - m)) * (1.0 - life);
  }
  o = over(o, body, smoothstep(0.03, -0.03, d));
