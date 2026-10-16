// Portalab — level_badge/toxic: the « toxic » effect (spec 028, B2)
  float surf = 0.55 + 0.06 * sin(p.x * 4.0 + t * 2.0) + 0.04 * sin(p.x * 9.0 - t * 3.0);
  float acid = fbm(p * 2.0 + vec2(0.0, -t * 0.6));
  vec3 body = mix(vec3(0.04, 0.22, 0.05), vec3(0.32, 0.85, 0.12), acid);
  body = mix(vec3(0.03, 0.08, 0.04), body, smoothstep(0.03, -0.03, p.y - surf));
  for (int i = 0; i < 6; i++) {
    float fi = float(i);
    float life = fract(t * (0.4 + 0.3 * hash(vec2(fi, 11.0))) + hash(vec2(fi, 12.0)));
    vec2 b = vec2((hash(vec2(fi, 13.0)) - 0.5) * 1.7 * ax, -0.9 + life * (surf + 0.9));
    float r = 0.07 + 0.07 * hash(vec2(fi, 14.0));
    float ring = smoothstep(r, r * 0.7, length(p - b)) - smoothstep(r * 0.7, r * 0.3, length(p - b)) * 0.7;
    body = mix(body, vec3(0.7, 1.0, 0.45), ring * 0.8);
  }
  body += vec3(0.6, 1.0, 0.3) * smoothstep(-0.2, 0.0, d) * 0.5;
  o = over(o, vec3(0.4, 1.0, 0.2), exp(-max(d, 0.0) * 3.5) * 0.4 * step(0.0, d));
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float x = (hash(vec2(fi, 15.0)) - 0.5) * 1.6 * ax;
    float life = fract(t * 0.35 + hash(vec2(fi, 16.0)));
    float y = -1.0 - life * life * 2.2;
    float drop = smoothstep(0.1, 0.0, length((p - vec2(x, y)) * vec2(1.0, 0.75))) * (1.0 - life);
    float thread = smoothstep(0.03, 0.0, abs(p.x - x)) * step(y, p.y) * step(p.y, -0.95) * step(life, 0.25);
    o = over(o, vec3(0.45, 1.0, 0.2), clamp(drop + thread, 0.0, 1.0));
  }
  o = over(o, body, smoothstep(0.03, -0.03, d));
