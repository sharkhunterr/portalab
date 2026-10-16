// Portalab — avatar_frame/sunburst: the « sunburst » effect (spec 028, B2)
  float s = atan(p.y, p.x / max(ax, 0.001));
  float r = max(d, 0.0);
  float rays = pow(0.5 + 0.5 * sin(s * 16.0 + t * 0.6), 6.0) + 0.6 * pow(0.5 + 0.5 * sin(s * 7.0 - t * 0.4 + 1.3), 4.0);
  float flare = exp(-r * (2.2 + 3.0 * (1.0 - min(rays, 1.0)))) * step(0.0, d);
  vec3 sun = mix(vec3(1.0, 0.45, 0.1), vec3(1.0, 0.92, 0.55), exp(-r * 3.0));
  o = over(o, sun, flare * (0.5 + 0.4 * noise(vec2(s * 6.0, t * 2.0))));
  vec3 body = mix(vec3(1.0, 0.55, 0.12), vec3(1.0, 0.93, 0.6), fbm(p * 2.5 + vec2(t * 0.3, -t * 0.2)));
  body += vec3(1.0, 1.0, 0.85) * smoothstep(-0.2, 0.0, d) * 0.4;
  o = over(o, body, smoothstep(0.03, -0.03, d));
