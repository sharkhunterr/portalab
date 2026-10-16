// Portalab — title/aqua: the « aqua » effect (spec 028, B2)
  float tilt = 0.3 * sin(t * 0.9) + 0.1 * sin(t * 2.3);
  float surf = -0.05 + tilt * p.x / ax + 0.1 * sin(p.x * 3.0 + t * 3.0) + 0.05 * sin(p.x * 7.0 - t * 4.2);
  float inside = smoothstep(0.03, -0.03, d);
  vec3 glass = vec3(0.05, 0.1, 0.18) + vec3(0.2, 0.35, 0.5) * smoothstep(-0.35, 0.0, d);
  o = over(o, glass, inside * 0.9);
  float water = smoothstep(0.02, -0.02, p.y - surf) * inside;
  float depth = clamp((surf - p.y) / 2.0, 0.0, 1.0);
  vec3 w = mix(vec3(0.15, 0.75, 0.95), vec3(0.02, 0.22, 0.55), depth);
  float caustic = 1.0 - abs(2.0 * fbm(p * 2.6 + vec2(t * 0.6, t * 0.35)) - 1.0);
  w += vec3(0.6, 0.95, 1.0) * smoothstep(0.88, 0.98, caustic) * (1.0 - depth) * 0.7;
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    float life = fract(t * (0.35 + 0.25 * hash(vec2(fi, 4.0))) + hash(vec2(fi, 5.0)));
    vec2 b = vec2((hash(vec2(fi, 6.0)) - 0.5) * 1.6 * ax + sin(life * 9.0 + fi) * 0.08, -0.95 + life * 1.5);
    float r = 0.06 + 0.06 * hash(vec2(fi, 7.0));
    float ring = smoothstep(r, r * 0.6, length(p - b)) - smoothstep(r * 0.6, r * 0.2, length(p - b)) * 0.6;
    w = mix(w, vec3(0.85, 0.97, 1.0), ring * step(b.y, surf) * 0.8);
  }
  o = over(o, w, water * 0.95);
  o = over(o, vec3(0.85, 0.98, 1.0), smoothstep(0.05, 0.0, abs(p.y - surf)) * inside * 0.9);
  o = over(o, vec3(0.75, 0.9, 1.0), smoothstep(0.08, 0.0, abs(d + 0.03)) * 0.9);
  vec2 hl = (p - vec2(-ax * 0.45, 0.55)) / vec2(ax * 0.35, 0.12);
  o = over(o, vec3(1.0), smoothstep(1.0, 0.3, length(hl)) * inside * 0.55);
  o = over(o, vec3(0.3, 0.75, 1.0), exp(-max(d, 0.0) * 5.0) * 0.35 * step(0.0, d));
