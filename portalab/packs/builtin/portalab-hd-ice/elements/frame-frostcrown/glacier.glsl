// Portalab — avatar_frame/frostcrown: the « glacier » effect (spec 028, B2)
  vec2 cell = floor(p * 2.2 + 0.5 * vec2(noise(p * 1.3), noise(p * 1.3 + 4.0)));
  float facet = hash(cell);
  vec3 ice = mix(vec3(0.1, 0.32, 0.55), vec3(0.35, 0.65, 0.88), facet) * (0.8 + 0.25 * noise(p * 6.0));
  ice += vec3(0.85, 0.95, 1.0) * smoothstep(-0.14, 0.0, d) * 0.6;
  float ang = atan(p.y, p.x / ax);
  float spikes = pow(abs(sin(ang * 9.0 + noise(vec2(ang * 3.0, 1.0)) * 3.0)), 6.0);
  float grow = 0.12 + 0.38 * spikes * (0.6 + 0.4 * sin(t * 0.7 + ang * 2.0));
  float frost = smoothstep(grow, grow * 0.3, d) * step(0.0, d) * (0.6 + 0.4 * noise(p * 12.0));
  o = over(o, vec3(0.7, 0.9, 1.0), exp(-max(d, 0.0) * 3.5) * 0.25 * step(0.0, d));
  o = over(o, vec3(0.85, 0.95, 1.0), frost * 0.9);
  o = over(o, ice, smoothstep(0.03, -0.03, d));
  vec2 gp = fract(p * 8.0) - 0.5;
  float glint = step(0.97, hash(floor(p * 8.0) + floor(t * 2.0)));
  float star = glint * (smoothstep(0.07, 0.0, abs(gp.x)) + smoothstep(0.07, 0.0, abs(gp.y))) * smoothstep(0.5, 0.0, length(gp));
  o = over(o, vec3(1.0), star * step(d, 0.35));
