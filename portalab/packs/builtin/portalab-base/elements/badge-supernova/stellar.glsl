// Portalab — badge/stellar: the « stellar » effect (spec 028, B2)
  vec2 w = vec2(fbm(p * 1.3 + vec2(t * 0.08, 0.0)), fbm(p * 1.3 + vec2(3.7, -t * 0.06)));
  float gas = fbm(p * 1.6 + w * 1.8 + vec2(0.0, t * 0.05));
  float dust = smoothstep(0.55, 0.78, fbm(p * 3.2 - w * 1.2 + 7.0));
  vec3 col = mix(vec3(0.05, 0.02, 0.12), vec3(0.85, 0.22, 0.55), smoothstep(0.3, 0.8, gas));
  col = mix(col, vec3(0.2, 0.78, 0.86), smoothstep(0.55, 0.9, w.x) * 0.7);
  col = mix(col, vec3(1.0, 0.86, 0.76), smoothstep(0.72, 0.95, gas) * 0.6);
  col *= 1.0 - dust * 0.6;
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    vec2 sp = vec2((hash(vec2(fi, 61.0)) - 0.5) * 1.6 * ax, (hash(vec2(fi, 62.0)) - 0.5) * 1.5);
    float tw = 0.6 + 0.4 * sin(t * (1.5 + fi * 0.4) + fi * 2.0);
    vec2 g = abs(p - sp);
    float star = exp(-length(g) * 26.0) + exp(-g.x * 90.0) * exp(-g.y * 9.0) * 0.5 + exp(-g.y * 90.0) * exp(-g.x * 9.0) * 0.5;
    col += vec3(1.0, 0.92, 0.98) * star * tw;
  }
  col += vec3(0.95, 0.5, 1.0) * smoothstep(-0.25, 0.0, d) * 0.45;
  float wisp = fbm(p * 1.8 + w * 1.4 + vec2(t * 0.12, -t * 0.05)) * exp(-max(d, 0.0) * 2.4) * step(0.0, d);
  vec3 haze = mix(vec3(0.9, 0.3, 0.65), vec3(0.3, 0.8, 0.9), smoothstep(0.4, 0.7, w.y));
  o = over(o, haze, smoothstep(0.25, 0.65, wisp) * 0.7);
  o = over(o, col, smoothstep(0.03, -0.03, d));
