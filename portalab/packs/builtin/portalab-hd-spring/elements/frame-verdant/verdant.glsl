// Portalab — avatar_frame/verdant: the « verdant » effect (spec 028, B2)
  float s = atan(p.y, p.x / max(ax, 0.001));
  float n = 9.0;
  float cell = floor((s + 3.14159) / 6.28318 * n);
  float local = fract((s + 3.14159) / 6.28318 * n) - 0.5 + 0.08 * sin(t * 1.3 + cell);
  float grow = 0.5 + 0.5 * sin(t * 0.8 + cell * 1.7);
  float len = 0.25 + 0.35 * grow;
  float r = max(d, 0.0);
  float k = clamp(r / len, 0.0, 1.0);
  float leaf = smoothstep(0.03, 0.0, abs(local) * 2.2 - sin(k * 3.14159) * 0.9) * step(r, len) * step(0.0, d);
  o = over(o, mix(vec3(0.2, 0.7, 0.3), vec3(0.78, 1.0, 0.45), k), leaf * 0.9);
  o = over(o, vec3(0.6, 1.0, 0.5), exp(-r * 4.0) * 0.3 * step(0.0, d));
  vec3 body = mix(vec3(0.03, 0.15, 0.06), vec3(0.2, 0.45, 0.2), fbm(p * 2.2 + t * 0.15));
  body += vec3(0.8, 1.0, 0.6) * smoothstep(-0.18, 0.0, d) * 0.5;
  o = over(o, body, smoothstep(0.03, -0.03, d));
  for (int i = 0; i < 8; i++) {
    float fi = float(i);
    float life = fract(t * 0.25 + hash(vec2(fi, 51.0)));
    vec2 pos = vec2((hash(vec2(fi, 52.0)) - 0.5) * 2.4 * ax + 0.1 * sin(life * 9.0), -1.0 + life * 2.6);
    o = over(o, vec3(1.0, 0.95, 0.5), smoothstep(0.05, 0.0, length(p - pos)) * sin(life * 3.14159));
  }
