// Portalab — notification_animation/eclipsed: the « totality » effect (spec 028, B2)
  float ang = atan(p.y, p.x / max(ax, 0.001));
  float r = max(d, 0.0);
  float streak = fbm(vec2(ang * 3.2, r * 1.5 - t * 0.08)) * 0.7 + 0.3 * noise(vec2(ang * 11.0, t * 0.2));
  float corona = exp(-r * (2.2 + 4.0 * (1.0 - streak))) * step(0.0, d);
  o = over(o, mix(vec3(0.75, 0.82, 1.0), vec3(1.0, 0.98, 0.94), exp(-r * 6.0)), corona * 0.85);
  float prom = smoothstep(0.62, 0.85, noise(vec2(ang * 7.0, t * 0.3))) * exp(-r * 22.0) * step(0.0, d);
  o = over(o, vec3(1.0, 0.35, 0.5), prom * 0.9);
  float cyc = mod(t, 8.0);
  float ring = exp(-abs(cyc - 7.0) * 3.0);
  float at = 2.3;
  vec2 rim = vec2(cos(at) * max(ax, 0.001), sin(at)) * 1.0;
  vec2 g = abs(p - rim);
  float diamond = (exp(-length(g) * 14.0) + exp(-g.x * 60.0) * exp(-g.y * 4.0) * 0.6 + exp(-g.y * 60.0) * exp(-g.x * 4.0) * 0.6) * ring;
  o = over(o, vec3(1.0, 0.98, 0.92), diamond);
  vec3 moon = vec3(0.015, 0.015, 0.03) + vec3(0.06, 0.07, 0.1) * fbm(p * 3.0) * 0.6;
  moon += vec3(0.85, 0.88, 1.0) * smoothstep(-0.06, 0.0, d) * 0.8;
  o = over(o, moon, smoothstep(0.03, -0.03, d));
