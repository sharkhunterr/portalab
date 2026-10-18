// Sheriff's star frame — the shape's frame (a star): p, d (< 0 inside), ax, t; writes into o. Polished gold
  // round the avatar, a glint running along it, its points tipped with little balls.
  float band = smoothstep(0.18, 0.0, abs(d - 0.05));
  float a = atan(p.y, p.x);
  vec3 gold = mix(vec3(0.62, 0.42, 0.12), vec3(1.0, 0.86, 0.45), 0.5 + 0.5 * sin(a * 5.0 + 1.0));
  o = over(o, gold, band * step(-0.02, d));
  float glint = exp(-abs(sin(a * 0.5 - t * 0.8)) * 18.0) * band;
  o = over(o, vec3(1.0, 0.97, 0.85), glint);
  float tips = smoothstep(0.08, 0.04, length(p - normalize(p + 0.0001) * (length(p) - d))) * step(0.9, 0.5 + 0.5 * cos(a * 5.0 - 1.5708));
  o = over(o, vec3(1.0, 0.9, 0.55), tips * step(0.0, d));
