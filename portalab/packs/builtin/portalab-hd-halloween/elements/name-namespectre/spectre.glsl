// Portalab — name_style/namespectre: the « spectre » effect (spec 028, B2)
  vec2 q = vec2(p.x * 1.2, p.y * 0.9 - t * 0.7);
  float wisp = fbm(q * 1.6 + vec2(fbm(q * 2.2 + t * 0.3) * 1.2, 0.0));
  float reach = 0.2 + 1.0 * smoothstep(-1.0, 1.5, p.y);
  float f = (1.2 - max(d, 0.0) / (reach * (0.4 + wisp))) * smoothstep(-0.2, 0.05, d);
  vec3 ghost = mix(vec3(0.15, 0.55, 0.5), vec3(0.78, 1.0, 0.93), smoothstep(0.4, 1.0, f));
  o = over(o, ghost, smoothstep(0.25, 0.7, f) * 0.85);
  vec3 body = mix(vec3(0.06, 0.03, 0.12), vec3(0.18, 0.36, 0.34), fbm(p * 2.0 + vec2(0.0, -t * 0.4)));
  body += vec3(0.5, 1.0, 0.85) * smoothstep(-0.2, 0.0, d) * 0.5;
  o = over(o, body, smoothstep(0.03, -0.03, d));
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float life = fract(t * 0.18 + hash(vec2(fi, 7.0)));
    vec2 pos = vec2((hash(vec2(fi, 8.0)) - 0.5) * 2.0 * ax, -0.6 + life * 2.4);
    float eyes = smoothstep(0.07, 0.0, length(p - pos - vec2(0.09, 0.0)))
      + smoothstep(0.07, 0.0, length(p - pos + vec2(0.09, 0.0)));
    o = over(o, vec3(0.8, 1.0, 0.9), eyes * sin(life * 3.14159) * 0.9);
  }
