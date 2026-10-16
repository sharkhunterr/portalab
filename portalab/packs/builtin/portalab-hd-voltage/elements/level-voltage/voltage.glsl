// Portalab — level_badge/voltage: the « voltage » effect (spec 028, B2)
  float flick = floor(t * 14.0);
  float pulse = 0.75 + 0.25 * noise(vec2(t * 9.0, 2.0));
  o = over(o, vec3(0.25, 0.45, 1.0), exp(-max(d, 0.0) * 3.2) * 0.45 * pulse * step(0.0, d));
  vec3 body = mix(vec3(0.03, 0.05, 0.16), vec3(0.08, 0.2, 0.5), fbm(p * 2.5 + t * 0.8));
  float inner = abs(fbm(p * 2.2 + vec2(flick * 0.37, flick * 0.21)) - 0.5);
  body += vec3(0.5, 0.85, 1.0) * smoothstep(0.03, 0.0, inner) * 0.9;
  body += vec3(0.4, 0.75, 1.0) * smoothstep(-0.3, 0.0, d) * 0.7;
  o = over(o, body, smoothstep(0.03, -0.03, d));
  float s = atan(p.y, p.x / ax);
  float glow = 0.0;
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float seg = step(0.45, noise(vec2(s * 1.6 + fi * 3.1, flick * 0.5 + fi * 7.0)));
    float off = 0.05 + 0.6 * noise(vec2(s * 7.0 + fi * 11.0, flick + fi * 5.0)) + 0.15 * noise(vec2(s * 23.0, flick * 1.3));
    float e = abs(d - off * (0.7 + 0.5 * fi));
    glow += seg * (0.02 / (e + 0.02)) * (0.85 - fi * 0.15);
  }
  o = over(o, vec3(0.35, 0.5, 1.0), smoothstep(0.15, 0.6, glow) * 0.35 * step(-0.05, d));
  o = over(o, mix(vec3(0.55, 0.75, 1.0), vec3(1.0), smoothstep(0.7, 1.4, glow)), smoothstep(0.45, 1.0, glow) * step(-0.05, d));
