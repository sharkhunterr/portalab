// Portalab — notification_style/magma: the « magma » effect (spec 028, B2)
  vec2 flow = vec2(t * 0.25, -t * 0.12);
  float v = fbm(p * 1.8 + flow + fbm(p * 2.7 - flow * 1.3) * 0.9);
  float crack = 1.0 - abs(2.0 * fbm(p * 2.4 + flow * 0.6 + 4.0) - 1.0);
  vec3 crust = mix(vec3(0.08, 0.03, 0.02), vec3(0.22, 0.08, 0.04), v);
  vec3 lava = mix(vec3(0.85, 0.2, 0.02), vec3(1.0, 0.75, 0.2), smoothstep(0.6, 0.9, v));
  float molten = smoothstep(0.82, 0.96, crack) + smoothstep(0.62, 0.8, v) * 0.6;
  vec3 body = mix(crust, lava, clamp(molten, 0.0, 1.0));
  body += vec3(1.0, 0.4, 0.05) * smoothstep(-0.2, 0.0, d) * 0.5;
  float heat = exp(-max(d, 0.0) * 3.0) * (0.55 + 0.25 * noise(vec2(t * 3.0, 1.0)));
  o = over(o, vec3(1.0, 0.35, 0.05), heat * 0.55 * step(0.0, d));
  o = over(o, body, smoothstep(0.03, -0.03, d));
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float life = fract(t * (0.4 + 0.2 * hash(vec2(fi, 8.0))) + hash(vec2(fi, 9.0)));
    vec2 s = vec2((hash(vec2(fi, 10.0)) - 0.5) * 2.0 * ax, 0.9 + life * 1.8);
    o = over(o, vec3(1.0, 0.55, 0.15), smoothstep(0.07, 0.0, length(p - s)) * (1.0 - life));
  }
