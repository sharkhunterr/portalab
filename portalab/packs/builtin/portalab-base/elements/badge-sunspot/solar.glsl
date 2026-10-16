// Portalab — badge/solar: the « solar » effect (spec 028, B2)
  float ang = atan(p.y, p.x / max(ax, 0.001));
  float r = max(d, 0.0);
  float streams = fbm(vec2(ang * 4.0, r * 2.5 - t * 0.3));
  o = over(o, vec3(1.0, 0.55, 0.15), exp(-r * (2.4 + 2.0 * (1.0 - streams))) * step(0.0, d) * 0.75);
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float a0 = hash(vec2(fi, 21.0)) * 6.2832 + t * 0.06 * (fi - 1.0);
    float da = mod(ang - a0 + 3.1416, 6.2832) - 3.1416;
    float x = da / (0.25 + 0.2 * hash(vec2(fi, 22.0)));
    float h = (0.25 + 0.3 * hash(vec2(fi, 23.0))) * (0.75 + 0.25 * sin(t * 0.6 + fi * 2.0));
    float arc = h * sqrt(max(0.0, 1.0 - x * x));
    float loop = smoothstep(0.07, 0.0, abs(r - arc)) * step(abs(x), 1.0) * step(0.0, d);
    o = over(o, mix(vec3(1.0, 0.3, 0.08), vec3(1.0, 0.75, 0.3), noise(vec2(ang * 20.0, t * 2.0))), loop * 0.85);
  }
  vec2 q = p * 2.4;
  float gran = fbm(q + vec2(fbm(q + t * 0.2), fbm(q - t * 0.15)) * 1.5);
  vec3 surf = mix(vec3(0.95, 0.42, 0.06), vec3(1.0, 0.88, 0.5), gran);
  surf += vec3(1.0, 0.95, 0.8) * smoothstep(-0.25, 0.0, d) * 0.45;
  o = over(o, surf, smoothstep(0.03, -0.03, d));
