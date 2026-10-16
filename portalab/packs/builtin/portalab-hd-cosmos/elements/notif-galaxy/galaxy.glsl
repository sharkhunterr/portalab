// Portalab — notification_style/galaxy: the « galaxy » effect (spec 028, B2)
  vec2 g = vec2(p.x / max(ax, 1.0) * 1.2, p.y);
  float r = length(g);
  float a = atan(g.y, g.x);
  float arms = sin(a * 2.0 - log(r + 0.05) * 4.0 + t * 0.8);
  float neb = fbm(g * 2.5 + vec2(t * 0.1, -t * 0.07));
  vec3 col = mix(vec3(0.04, 0.02, 0.1), vec3(0.45, 0.12, 0.6), smoothstep(-0.2, 1.0, arms) * (1.0 - smoothstep(0.2, 1.4, r)));
  col += vec3(0.15, 0.3, 0.85) * neb * 0.5;
  col += vec3(1.0, 0.85, 0.95) * exp(-r * 6.0) * 0.9;
  vec2 sg = p * 9.0;
  float sh = hash(floor(sg));
  col += vec3(1.0) * step(0.92, sh) * smoothstep(0.35, 0.0, length(fract(sg) - 0.5)) * (0.5 + 0.5 * sin(t * 3.0 + sh * 40.0));
  col += vec3(0.6, 0.4, 1.0) * smoothstep(-0.25, 0.0, d) * 0.6;
  o = over(o, vec3(0.55, 0.3, 1.0), exp(-max(d, 0.0) * 4.0) * 0.4 * step(0.0, d));
  o = over(o, col, smoothstep(0.03, -0.03, d));
