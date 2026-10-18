// Zeus's shield frame — the shape's frame (a shield): p, d (< 0 inside), ax, t; writes into o. Bronze round the
  // avatar, a Greek key engraved on it, blue lightning crawling along the rim.
  float band = smoothstep(0.2, 0.0, abs(d - 0.06));
  float a = atan(p.y, p.x);
  vec3 bronze = mix(vec3(0.55, 0.36, 0.15), vec3(0.95, 0.75, 0.4), 0.5 + 0.5 * sin(a * 3.0 + p.y * 4.0));
  o = over(o, bronze, band * step(-0.02, d));
  float key = step(0.5, fract(a * 6.0)) * smoothstep(0.03, 0.0, abs(d - 0.06)) * 0.5;
  o = over(o, vec3(0.35, 0.22, 0.08), key);
  float arc = abs(d - 0.12 - 0.03 * (noise(vec2(a * 8.0, t * 6.0)) - 0.5));
  float live = step(0.4, noise(vec2(a * 2.0 - t * 1.5, 3.0)));
  o = over(o, vec3(0.65, 0.85, 1.0), smoothstep(0.02, 0.0, arc) * live);
  o = over(o, vec3(0.4, 0.6, 1.0), smoothstep(0.08, 0.0, arc) * live * 0.4);
