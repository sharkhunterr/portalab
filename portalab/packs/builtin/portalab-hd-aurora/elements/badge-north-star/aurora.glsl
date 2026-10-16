// Portalab — badge/aurora: the « aurora » effect (spec 028, B2)
  vec3 body = mix(vec3(0.01, 0.03, 0.09), vec3(0.03, 0.09, 0.2), p.y * 0.5 + 0.5);
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float x = p.x * 0.8 + fbm(vec2(p.x * 0.7 + fi * 3.0, t * 0.15)) * 1.5;
    float centre = 0.1 + 0.25 * sin(x * 2.0 + t * 0.5 + fi * 2.0);
    float curtain = exp(-pow((p.y - centre) * 2.6, 2.0)) * smoothstep(-1.0, centre, p.y);
    float rays = 0.55 + 0.45 * sin(p.x * 22.0 + fbm(vec2(p.x * 3.0, t * 0.3 + fi)) * 10.0);
    vec3 c = fi < 0.5 ? vec3(0.2, 1.0, 0.55) : fi < 1.5 ? vec3(0.2, 0.85, 0.9) : vec3(0.65, 0.35, 1.0);
    body += c * curtain * rays * 0.55;
  }
  vec2 sg = p * 8.0;
  body += vec3(1.0) * step(0.95, hash(floor(sg))) * smoothstep(0.3, 0.0, length(fract(sg) - 0.5)) * 0.8;
  body += vec3(0.5, 1.0, 0.8) * smoothstep(-0.15, 0.0, d) * 0.45;
  o = over(o, vec3(0.3, 1.0, 0.6), exp(-max(d, 0.0) * 4.5) * 0.3 * step(0.0, d));
  o = over(o, body, smoothstep(0.03, -0.03, d));
