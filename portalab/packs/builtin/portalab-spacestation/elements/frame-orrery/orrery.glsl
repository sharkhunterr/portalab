// Portalab — avatar_frame/orrery: the « orrery » effect (spec 028, B2)
  vec2 e = vec2(p.x / max(ax, 0.001), p.y);
  vec3 sky = mix(vec3(0.02, 0.03, 0.09), vec3(0.06, 0.05, 0.16), smoothstep(1.2, 0.0, length(e)));
  vec2 sg = p * 11.0;
  sky += vec3(0.9) * step(0.95, hash(floor(sg))) * smoothstep(0.35, 0.0, length(fract(sg) - 0.5)) * (0.5 + 0.5 * sin(t * 2.0 + hash(floor(sg)) * 30.0));
  float sun = length(e);
  sky += vec3(1.0, 0.75, 0.3) * exp(-sun * 7.0) * (0.9 + 0.1 * sin(t * 3.0));
  sky += vec3(1.0, 0.95, 0.8) * smoothstep(0.13, 0.1, sun);
  sky += vec3(0.6, 0.7, 1.0) * smoothstep(-0.2, 0.0, d) * 0.35;
  o = over(o, vec3(1.0, 0.75, 0.35), exp(-max(d, 0.0) * 4.0) * 0.25 * step(0.0, d));
  o = over(o, sky, smoothstep(0.03, -0.03, d));
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float rad = 0.42 + 0.3 * fi + (fi > 1.5 ? 0.18 : 0.0);
    vec2 orbit = vec2(rad * max(ax, 1.0) * (fi > 1.5 ? 1.0 : 0.85), rad);
    float ring = abs(length(p / orbit) - 1.0) * rad;
    o = over(o, vec3(0.55, 0.65, 0.95), smoothstep(0.018, 0.0, ring) * 0.3);
    float a = t * (0.9 - 0.18 * fi) + fi * 1.7;
    vec2 at = vec2(cos(a), sin(a)) * orbit;
    float size = 0.07 + 0.035 * mod(fi * 3.0, 4.0) * 0.5;
    float dp = length(p - at);
    vec3 hue = fi < 0.5 ? vec3(0.85, 0.55, 0.35) : fi < 1.5 ? vec3(0.35, 0.6, 1.0) : fi < 2.5 ? vec3(0.95, 0.4, 0.3) : vec3(0.9, 0.78, 0.55);
    float lit = 0.35 + 0.65 * smoothstep(-0.6, 0.8, dot(normalize(-at), normalize(p - at + 1e-4)));
    o = over(o, hue * lit, smoothstep(size, size * 0.8, dp));
    o = over(o, hue, exp(-max(dp - size, 0.0) * 30.0) * 0.25);
  }
