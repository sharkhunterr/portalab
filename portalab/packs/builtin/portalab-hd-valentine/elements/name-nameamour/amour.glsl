// Portalab — name_style/nameamour: the « amour » effect (spec 028, B2)
  float sw = fbm(vec2(atan(p.y, p.x) * 2.0 + t * 0.6, length(p) * 2.0 - t * 0.8));
  vec3 glow = mix(vec3(0.9, 0.15, 0.35), vec3(1.0, 0.6, 0.75), sw);
  o = over(o, glow, exp(-max(d, 0.0) * 3.5) * (0.35 + 0.4 * sw) * step(0.0, d));
  vec3 body = mix(vec3(0.3, 0.02, 0.1), vec3(0.85, 0.2, 0.4), fbm(p * 2.0 + vec2(t * 0.3, 0.0)));
  body += vec3(1.0, 0.7, 0.8) * smoothstep(-0.18, 0.0, d) * 0.5;
  o = over(o, body, smoothstep(0.03, -0.03, d));
  for (int i = 0; i < 8; i++) {
    float fi = float(i);
    float life = fract(t * 0.2 * (1.0 + hash(vec2(fi, 41.0))) + hash(vec2(fi, 42.0)));
    vec2 pos = vec2((hash(vec2(fi, 43.0)) - 0.5) * 2.2 * ax + 0.15 * sin(life * 8.0 + fi), -1.1 + life * 2.8);
    vec2 h = (p - pos) / 0.12;
    h.x = abs(h.x);
    float hd = length(vec2(h.x, h.y - sqrt(h.x) * 0.55)) - 1.0;
    o = over(o, vec3(1.0, 0.35, 0.55), smoothstep(0.12, -0.12, hd) * sin(life * 3.14159) * 0.95);
  }
