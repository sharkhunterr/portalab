// Portalab — name_style/nameshadow: the « shadow » effect (spec 028, B2)
  float smoke = fbm(p * 1.8 + vec2(t * 0.3, t * 0.5) + fbm(p * 2.5 - t * 0.2));
  float reach = 0.15 + 0.7 * smoke;
  o = over(o, vec3(0.5, 0.0, 0.05), exp(-abs(d - reach * 0.6) * 10.0) * 0.18 * step(0.0, d));
  o = over(o, vec3(0.02, 0.0, 0.02), smoothstep(reach, 0.0, d) * step(0.0, d) * 0.85);
  vec3 body = vec3(0.03, 0.01, 0.03);
  body += vec3(0.5, 0.02, 0.05) * smoothstep(0.93, 0.99, 1.0 - abs(2.0 * fbm(p * 3.0 + t * 0.1) - 1.0));
  float blink = step(0.08, abs(fract(t * 0.23) - 0.5));
  float open = smoothstep(0.0, 0.4, fract(t * 0.11)) * blink;
  for (int j = 0; j < 2; j++) {
    vec2 e = p - vec2((j == 0 ? -0.35 : 0.35) * min(ax, 1.5), 0.15);
    float eye = smoothstep(0.0, 0.2, 1.0 - length(vec2(e.x / 0.16, e.y / (0.07 * max(open, 0.05)) + abs(e.x) * 4.0)));
    body = mix(body, vec3(1.0, 0.15, 0.05), eye);
  }
  body += vec3(0.4, 0.0, 0.05) * smoothstep(-0.15, 0.0, d) * 0.6;
  o = over(o, body, smoothstep(0.03, -0.03, d));
