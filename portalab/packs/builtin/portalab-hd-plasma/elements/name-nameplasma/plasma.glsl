// Portalab — name_style/nameplasma: the « plasma » effect (spec 028, B2)
  vec2 c = vec2(p.x / max(ax, 1.0), p.y);
  float r = length(c);
  float a = atan(c.y, c.x);
  float fil = 0.0;
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    float phi = fi * 1.2566 + t * 0.4 + (noise(vec2(r * 4.0, t * 1.5 + fi * 3.0)) - 0.5) * 1.6;
    float da = abs(mod(a - phi + 3.1416, 6.2831) - 3.1416);
    fil += 0.03 / (da * r * 3.0 + 0.03) * smoothstep(1.05, 0.15, r);
  }
  vec3 body = vec3(0.06, 0.01, 0.12) + vec3(1.0, 0.3, 0.9) * fil * 0.35 + vec3(1.0, 0.85, 1.0) * exp(-r * 5.0);
  body += vec3(0.8, 0.6, 1.0) * smoothstep(-0.12, 0.0, d) * 0.55;
  o = over(o, vec3(0.9, 0.3, 1.0), exp(-max(d, 0.0) * 4.5) * 0.4 * step(0.0, d));
  o = over(o, body, smoothstep(0.03, -0.03, d));
