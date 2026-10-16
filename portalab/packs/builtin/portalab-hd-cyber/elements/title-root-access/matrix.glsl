// Portalab — title/matrix: the « matrix » effect (spec 028, B2)
  vec2 g = p * 4.0;
  float col = floor(g.x);
  float sp = 1.5 + 2.0 * hash(vec2(col, 1.0));
  vec2 cell = vec2(col, floor(g.y + t * sp));
  float stream = pow(fract(g.y * 0.17 + t * sp * 0.25 + hash(vec2(col, 3.0))), 3.0);
  vec2 f = fract(vec2(g.x, g.y + t * sp));
  vec2 sub = floor(f * 3.0);
  float bit = step(0.4, hash(cell * 1.3 + sub + floor(t * 5.0 + hash(cell) * 3.0)));
  float glyph = bit * step(0.12, f.x) * step(f.x, 0.88) * step(0.12, f.y) * step(f.y, 0.88);
  vec3 body = vec3(0.0, 0.05, 0.02) + vec3(0.15, 0.95, 0.35) * glyph * stream;
  body += vec3(0.8, 1.0, 0.85) * glyph * step(0.94, stream);
  body += vec3(0.2, 1.0, 0.4) * smoothstep(-0.12, 0.0, d) * 0.5;
  o = over(o, vec3(0.1, 1.0, 0.35), exp(-max(d, 0.0) * 5.0) * 0.35 * step(0.0, d));
  o = over(o, body, smoothstep(0.03, -0.03, d));
